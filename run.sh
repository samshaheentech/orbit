#!/bin/bash
# orbit/run.sh — core runner
# Called by launchd on schedule. Works queue/, writes every action to briefs/data/events.jsonl
# Test by hand from anywhere: bash ~/git/orbit/run.sh

set -euo pipefail

ORBIT_HOME="${ORBIT_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
CONFIG="$ORBIT_HOME/config/user.md"
SYSTEM_PROMPT="$ORBIT_HOME/system/prompt.md"

# Tunables (override via env or launchd EnvironmentVariables)
MAX_TASKS_PER_RUN="${MAX_TASKS_PER_RUN:-2}"
TASK_TIMEOUT_SEC="${TASK_TIMEOUT_SEC:-5400}"      # 90 min hard wall clock per task
DEFAULT_MAX_TURNS="${DEFAULT_MAX_TURNS:-60}"
DEFAULT_MODEL="${DEFAULT_MODEL:-claude-sonnet-5}"
DEFAULT_EFFORT="${DEFAULT_EFFORT:-medium}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-4}"                  # before task is parked in blocked/

# Paths
Q="$ORBIT_HOME/queue"
RUN="$ORBIT_HOME/running"
DONE="$ORBIT_HOME/done"
BLOCKED="$ORBIT_HOME/blocked"
LOGS="$ORBIT_HOME/logs"
STATE="$ORBIT_HOME/state"
WORKTREES="$ORBIT_HOME/worktrees"
EVENTS="$ORBIT_HOME/briefs/data/events.jsonl"

export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# ---- default allowed tools ----
DEFAULT_TOOLS='Read,Edit,Write,Glob,Grep,Bash(git status *),Bash(git diff *),Bash(git log *),Bash(git show *),Bash(git add *),Bash(git commit *),Bash(git branch *),Bash(git rev-parse *),Bash(git stash *),Bash(make *),Bash(cmake *),Bash(ninja *),Bash(ctest *),Bash(pytest *),Bash(python3 *),Bash(node *),Bash(npm test *),Bash(npm run *),Bash(ls *),Bash(cat *),Bash(find *),Bash(wc *),Bash(curl *),Bash(jq *)'

# ---- helpers ----
STAMP="$(date +%Y-%m-%dT%H:%M:%S)"
FIRE_ID="fire-$(date +%Y%m%d-%H%M%S)"

log_event() {
  # log_event <type> <lane> <task> <status> <model> <cost> <tokens_est> <tokens_actual> <note> [<extra json object>]
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  TS="$ts" FIRE="$FIRE_ID" T="$1" L="$2" K="$3" S="$4" M="$5" C="${6:-0}" TE="${7:-0}" TA="${8:-0}" N="${9:-}" X="${10:-{\}}" python3 - >> "$EVENTS" <<'PY'
import json, os
def num(v):
    try: return float(v) if "." in str(v) else int(v)
    except ValueError: return 0
e = {"ts": os.environ["TS"], "fire": os.environ["FIRE"], "type": os.environ["T"], "lane": os.environ["L"], "task": os.environ["K"],
     "status": os.environ["S"], "model": os.environ["M"], "cost_usd": num(os.environ["C"]), "tokens_est": num(os.environ["TE"]),
     "tokens_actual": num(os.environ["TA"]), "note": os.environ["N"]}
try: e.update(json.loads(os.environ.get("X") or "{}"))
except ValueError: pass
print(json.dumps(e))
PY
}

fm() { sed -n '2,/^---$/p' "$1" | sed -n "s/^$2:[[:space:]]*//p" | head -1 | sed 's/[[:space:]]*#.*$//'; }

jf() {
  if command -v jq >/dev/null 2>&1; then
    jq -r ".$2 // empty" "$1" 2>/dev/null
  else
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); v=d.get(sys.argv[2]); print("" if v is None else (json.dumps(v) if isinstance(v,bool) else str(v)))' "$1" "$2" 2>/dev/null
  fi
}

model_flag() {
  # Map a task's frontmatter model: value to a string the CLI's --model flag accepts.
  # Claude Code takes either a short alias (sonnet, opus, haiku, fable) or a full model ID
  # (claude-sonnet-5, claude-fable-5-1, claude-haiku-4-5-20251001, ...); both are valid, but
  # full IDs are what Anthropic recommends for unattended automation, so that is what we emit
  # for our own three models. Anything already alias-shaped or already a full "claude-*" ID is
  # passed through untouched, so a task can also just say "model: sonnet" or a literal ID.
  case "$1" in
    fable*)              echo "claude-fable-5-1" ;;
    sonnet-5|sonnet5)    echo "claude-sonnet-5" ;;
    haiku*)              echo "claude-haiku-4-5-20251001" ;;
    claude-*)            echo "$1" ;;
    sonnet|opus|best|opusplan) echo "$1" ;;
    ""|*)                echo "$DEFAULT_MODEL" ;;
  esac
}

effort_turns() {
  # Map effort level to max_turns if not set in frontmatter
  case "$1" in
    low)    echo 20 ;;
    medium) echo 60 ;;
    high)   echo 100 ;;
    max)    echo 200 ;;
    *)      echo "$DEFAULT_MAX_TURNS" ;;
  esac
}

run_with_timeout() {
  local secs=$1; shift
  "$@" & local pid=$!
  ( sleep "$secs"; kill -TERM "$pid" 2>/dev/null ) & local wd=$!
  wait "$pid"; local rc=$?
  kill "$wd" 2>/dev/null; wait "$wd" 2>/dev/null || true
  return $rc
}

notify() {
  osascript -e "display notification \"$2\" with title \"Orbit\" subtitle \"$1\"" >/dev/null 2>&1 || true
}

# ---- single instance lock ----
LOCK="$ORBIT_HOME/.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  if kill -0 "$(cat "$LOCK/pid" 2>/dev/null)" 2>/dev/null; then
    log_event "fire_skipped" "" "" "locked" "" 0 0 0 "another instance running"
    exit 0
  fi
  rm -rf "$LOCK"; mkdir "$LOCK"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

command -v claude >/dev/null 2>&1 || { notify "not running" "claude not on PATH"; exit 1; }

# ---- window decision (Fire 10). launchd polls every 15 minutes; this decides whether to work.
#      ORBIT_MANUAL=1 (orbit fire) skips the window logic and runs the old two-task fire.
MODE="fire"; DEADLINE_EPOCH=0; BUDGET_LEFT="999999"; STARTS_WINDOW="false"; DECISION="{}"
if [ -z "${ORBIT_MANUAL:-}" ]; then
  DECISION="$(python3 "$ORBIT_HOME/system/window.py" decide 2>/dev/null || echo '{"mode":"fire"}')"
  MODE="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode","fire"))' 2>/dev/null || echo fire)"
  DEADLINE_EPOCH="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("deadline_epoch",0))' 2>/dev/null || echo 0)"
  BUDGET_LEFT="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("budget_left_usd",999999))' 2>/dev/null || echo 999999)"
  STARTS_WINDOW="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("starts_window",False)).lower())' 2>/dev/null || echo false)"
  if [ "$MODE" != "fire" ]; then exit 0; fi     # idle: nothing logged, nothing spent
  SWEEP="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("sweep",True)).lower())' 2>/dev/null || echo true)"
  if [ "$SWEEP" = "true" ]; then
    MAX_TASKS_PER_RUN=99                        # plan: max — drain the window's budget
  else
    MAX_TASKS_PER_RUN="$(printf '%s' "$DECISION" | python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("max_tasks_per_fire",2)))' 2>/dev/null || echo 2)"
    DEADLINE_EPOCH=0; BUDGET_LEFT="999999"      # plan: pro / fixed — a plain capped fire, no sweep economics
  fi
fi

log_event "fire_start" "" "" "running" "" 0 0 0 "$(printf '%s' "$DECISION" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("reason","manual"))' 2>/dev/null || echo manual)"
if [ "$STARTS_WINDOW" = "true" ]; then
  log_event "window_start" "" "" "open" "" 0 0 0 "orbit started this window" "$(printf '%s' "$DECISION" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"reset_at": d.get("reset_at"), "budget_usd": d.get("budget_usd")}))' 2>/dev/null || echo '{}')"
fi

# ---- check for tasks ----
PENDING=0
for f in "$Q"/*.md; do
  [ -e "$f" ] || break
  case "$(basename "$f")" in _*) ;; *) PENDING=$((PENDING+1));; esac
done

if [ "$PENDING" -eq 0 ]; then
  log_event "fire_end" "" "" "empty_queue" "" 0 0 0 "no tasks"
  notify "queue empty" "nothing to do"
  exit 0
fi

FIRE_COST_TOTAL=0
PROCESSED=0
FIRE_SUMMARY=""
STOP=0

# ---- main task loop ----
# Order: light tasks first, heavy tasks (weight: heavy, or Fable) last. After a usage limit in the last
# 5 hours, heavy tasks are skipped this fire (logged once) so the window recovers on light work.
LIMIT_RECENT=0
if [ -f "$EVENTS" ] && python3 - "$EVENTS" <<'PY'
import json, sys, datetime as dt
now = dt.datetime.utcnow(); hit = False
for l in open(sys.argv[1], encoding="utf-8"):
    try: e = json.loads(l)
    except ValueError: continue
    if e.get("type") == "fire_limit" and now - dt.datetime.strptime(e["ts"][:19], "%Y-%m-%dT%H:%M:%S") < dt.timedelta(hours=5): hit = True
sys.exit(0 if hit else 1)
PY
then LIMIT_RECENT=1; fi
PULLS=0; STOP_FIRE=0
while :; do
ORDERED="$(for f in "$Q"/*.md; do [ -e "$f" ] || continue; w="$(fm "$f" weight)"; m="$(fm "$f" model)"; case "$w$m" in *heavy*|*fable*) echo "1 $f";; *) echo "0 $f";; esac; done | sort -k1,1 -k2,2 | cut -d' ' -f2-)"
for TASK_FILE in $ORDERED; do
  [ "$STOP_FIRE" -eq 1 ] && break
  [ -e "$TASK_FILE" ] || break
  [ "$STOP" -eq 1 ] && break
  [ "$PROCESSED" -ge "$MAX_TASKS_PER_RUN" ] && break

  NAME="$(basename "$TASK_FILE" .md)"
  case "$NAME" in _*) continue;; esac

  # Read frontmatter
  LANE="$(fm "$TASK_FILE" lane)";       LANE="${LANE:-general}"
  RAW_MODEL="$(fm "$TASK_FILE" model)"; MODEL="$(model_flag "$RAW_MODEL")"
  EFFORT="$(fm "$TASK_FILE" effort)";   EFFORT="${EFFORT:-$DEFAULT_EFFORT}"
  MAX_TURNS_FM="$(fm "$TASK_FILE" max_turns)"
  MAX_TURNS="${MAX_TURNS_FM:-$(effort_turns "$EFFORT")}"
  EXTRA_TOOLS="$(fm "$TASK_FILE" tools)"
  TOOLS="$DEFAULT_TOOLS${EXTRA_TOOLS:+,$EXTRA_TOOLS}"
  DIR="$(fm "$TASK_FILE" dir)"; DIR="${DIR:-$HOME}"; DIR="${DIR/#\~/$HOME}"
  EXEC="$(fm "$TASK_FILE" exec)"   # exec: <path> runs python3 <path> from ORBIT_HOME instead of claude -p

  # days: / hours: gates. A task that isn't due stays in the queue untouched (no attempt, no log line).
  DAYS="$(fm "$TASK_FILE" days | tr 'A-Z' 'a-z' | tr -d ' ')"; HOURS="$(fm "$TASK_FILE" hours | tr -d ' ')"
  TODAY="$(date +%a | tr 'A-Z' 'a-z')"; HOURNOW="$(date +%H)"; HOURNOW="${HOURNOW#0}"
  if [ -n "$DAYS" ] && ! printf ',%s,' "$DAYS" | grep -q ",$TODAY,"; then continue; fi
  if [ -n "$HOURS" ] && ! printf ',%s,' "$HOURS" | grep -q ",${HOURNOW:-0},"; then continue; fi

  # requires_mcp: <name>. Without a configured MCP server matching <name>, the task stays in the queue
  # and one task_blocked event is logged per fire so the brief keeps pointing at the lane's SETUP.md.
  REQ_MCP="$(fm "$TASK_FILE" requires_mcp)"
  if [ -n "$REQ_MCP" ]; then
    [ -n "${MCP_LIST+x}" ] || MCP_LIST="$(claude mcp list 2>/dev/null || true)"
    if ! printf '%s' "$MCP_LIST" | grep -qi "$REQ_MCP"; then
      log_event "task_blocked" "$LANE" "$NAME" "mcp_missing" "" 0 0 0 "needs MCP server '$REQ_MCP'; see config/lanes/$LANE/SETUP.md"
      FIRE_SUMMARY="$FIRE_SUMMARY $NAME:NEEDS-MCP"
      continue
    fi
  fi

  if [ ! -d "$DIR" ]; then
    log_event "task_blocked" "$LANE" "$NAME" "dir_missing" "$MODEL" 0 0 0 "dir not found: $DIR"
    mv "$TASK_FILE" "$BLOCKED/"
    FIRE_SUMMARY="$FIRE_SUMMARY $NAME:BLOCKED"
    continue
  fi

  # Attempt tracking
  ATT=$(( $(cat "$STATE/$NAME.attempts" 2>/dev/null || echo 0) + 1 ))
  echo "$ATT" > "$STATE/$NAME.attempts"
  if [ "$ATT" -gt "$MAX_ATTEMPTS" ]; then
    log_event "task_blocked" "$LANE" "$NAME" "max_attempts" "$MODEL" 0 0 0 "exceeded $MAX_ATTEMPTS attempts"
    mv "$TASK_FILE" "$BLOCKED/"
    FIRE_SUMMARY="$FIRE_SUMMARY $NAME:BLOCKED"
    continue
  fi

  # Git worktree per task (if inside a repo)
  WT="$DIR"; BRANCH="(no-git)"
  if [ -z "$EXEC" ] && git -C "$DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    TOP="$(git -C "$DIR" rev-parse --show-toplevel)"
    BRANCH="agent/$NAME"
    WT="$WORKTREES/$(basename "$TOP")-$NAME"
    if [ ! -d "$WT" ]; then
      if git -C "$TOP" show-ref --verify --quiet "refs/heads/$BRANCH"; then
        git -C "$TOP" worktree add "$WT" "$BRANCH" >/dev/null 2>&1
      else
        git -C "$TOP" worktree add -b "$BRANCH" "$WT" >/dev/null 2>&1
      fi
    fi
    [ -d "$WT" ] || { WT="$DIR"; BRANCH="(worktree-failed)"; }
  fi

  mv "$TASK_FILE" "$RUN/"
  TASK_FILE="$RUN/$NAME.md"
  OUT="$LOGS/$FIRE_ID-$NAME.json"
  ERR="$LOGS/$FIRE_ID-$NAME.err"

  # Build prompt
  SID="$(cat "$STATE/$NAME.session" 2>/dev/null || echo "")"
  CONT=""
  [ "$ATT" -gt 1 ] && CONT="Attempt $ATT. Previous run worked in this worktree — check git log and git status first, then continue where it left off.
"
  export ORBIT_FIRE="$FIRE_ID" ORBIT_LANE="$LANE" ORBIT_TASK="$NAME" ORBIT_HOME
  PROMPT="User config: $CONFIG
Task file: $TASK_FILE
Working tree: $WT  Branch: $BRANCH
Allowed tools: $TOOLS
Deliver anything the user should see through the emitter, never by editing events.jsonl: python3 $ORBIT_HOME/system/emit.py (contract: $ORBIT_HOME/system/data-contract.md)

${CONT}$(cat "$TASK_FILE")"

  # Estimate tokens (rough: ~3 tokens/char of prompt)
  WEIGHT="$(fm "$TASK_FILE" weight)"; case "$WEIGHT$MODEL" in *heavy*|*fable*) IS_HEAVY=1;; *) IS_HEAVY=0;; esac
  if [ "$LIMIT_RECENT" -eq 1 ] && [ "$IS_HEAVY" -eq 1 ]; then
    log_event "task_skipped" "$LANE" "$NAME" "limit_recovery" "$MODEL" 0 0 0 "heavy task skipped: usage limit hit in the last 5h"
    mv "$TASK_FILE" "$Q/$NAME.md"; ATT=$((ATT-1)); echo "$ATT" > "$STATE/$NAME.attempts"; continue
  fi
  PROMPT_CHARS="${#PROMPT}"
  EST_JSON="$(python3 "$ORBIT_HOME/system/estimate.py" predict --task "$NAME" --lane "$LANE" --model "$MODEL" --body-chars "$PROMPT_CHARS" 2>/dev/null || echo '{}')"
  COST_EST="$(printf '%s' "$EST_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("cost_est",0))' 2>/dev/null || echo 0)"
  TOKENS_EST="$(printf '%s' "$EST_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tokens_est",0))' 2>/dev/null || echo 0)"

  if [ -z "${ORBIT_MANUAL:-}" ]; then
    SECS_EST="$(printf '%s' "$EST_JSON" | python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("secs_est",1200)))' 2>/dev/null || echo 1200)"
    NOW_EPOCH="$(date +%s)"
    if [ "$DEADLINE_EPOCH" -gt 0 ] && [ $((NOW_EPOCH + SECS_EST)) -gt "$DEADLINE_EPOCH" ]; then
      log_event "fire_stop" "$LANE" "$NAME" "deadline" "$MODEL" 0 0 0 "not enough time before reset for $NAME (est ${SECS_EST}s)"
      mv "$TASK_FILE" "$Q/$NAME.md"; ATT=$((ATT-1)); echo "$ATT" > "$STATE/$NAME.attempts"; STOP_FIRE=1; break
    fi
    if python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) + float(sys.argv[2]) > float(sys.argv[3]) else 1)' "$FIRE_COST_TOTAL" "$COST_EST" "$BUDGET_LEFT" 2>/dev/null; then
      log_event "fire_stop" "$LANE" "$NAME" "budget" "$MODEL" 0 0 0 "window budget reached (spent \$$FIRE_COST_TOTAL of \$$BUDGET_LEFT left; $NAME est \$$COST_EST)"
      mv "$TASK_FILE" "$Q/$NAME.md"; ATT=$((ATT-1)); echo "$ATT" > "$STATE/$NAME.attempts"; STOP_FIRE=1; break
    fi
  fi

  log_event "task_start" "$LANE" "$NAME" "running" "$MODEL" 0 "$TOKENS_EST" 0 "attempt $ATT" "{\"cost_est\": $COST_EST}"

  START_SEC=$(date +%s)
  if [ -n "$EXEC" ]; then
    # exec: task. The script runs directly from ORBIT_HOME; its stdout is the result and ends
    # with the same STATUS block. An optional "COST_USD: <n>" line reports what it spent.
    OUT="${OUT%.json}.txt"
    ( cd "$ORBIT_HOME" && run_with_timeout "$TASK_TIMEOUT_SEC" \
      python3 "$ORBIT_HOME/$EXEC" > "$OUT" 2> "$ERR" ) && RC=0 || RC=$?
    ELAPSED=$(( $(date +%s) - START_SEC ))
    RESULT="$(cat "$OUT" 2>/dev/null || true)"
    IS_ERR="false"; if [ "$RC" -ne 0 ] && [ "$RC" -ne 143 ]; then IS_ERR="true"; fi
    COST="$(printf '%s\n' "$RESULT" | sed -n 's/^COST_USD:[[:space:]]*//p' | tail -1)"
    case "$COST" in ''|*[!0-9.]*) COST=0;; esac
    NEW_SID=""
  else
  ( cd "$WT" && run_with_timeout "$TASK_TIMEOUT_SEC" \
    claude -p "$PROMPT" \
      --append-system-prompt-file "$SYSTEM_PROMPT" \
      --permission-mode acceptEdits \
      --allowedTools "$TOOLS" \
      --max-turns "$MAX_TURNS" \
      --model "$MODEL" \
      ${SID:+--resume "$SID"} \
      --output-format json \
      > "$OUT" 2> "$ERR" )
  RC=$?
  ELAPSED=$(( $(date +%s) - START_SEC ))

  RESULT="$(jf "$OUT" result)"
  IS_ERR="$(jf "$OUT" is_error)"
  COST="$(jf "$OUT" total_cost_usd)"; COST="${COST:-0}"
  NEW_SID="$(jf "$OUT" session_id)"
  USAGE_JSON="$(python3 - "$OUT" <<'PY' 2>/dev/null || echo '{}'
import json, sys
try: u = json.load(open(sys.argv[1])).get("usage") or {}
except Exception: u = {}
print(json.dumps({"tokens_in": u.get("input_tokens", 0), "tokens_out": u.get("output_tokens", 0),
                  "tokens_cache_read": u.get("cache_read_input_tokens", 0), "tokens_cache_write": u.get("cache_creation_input_tokens", 0)}))
PY
)"
  fi
  USAGE_JSON="${USAGE_JSON:-{\}}"
  TOKENS_ACTUAL="$(printf '%s' "$USAGE_JSON" | python3 -c 'import json,sys; u=json.load(sys.stdin); print(int(u.get("tokens_in",0))+int(u.get("tokens_out",0)))' 2>/dev/null || echo 0)"
  [ "$IS_ERR" != "true" ] && [ -n "$NEW_SID" ] && echo "$NEW_SID" > "$STATE/$NAME.session"

  FIRE_COST_TOTAL="$(awk -v a="$FIRE_COST_TOTAL" -v b="$COST" 'BEGIN{printf "%.4f", a+b}')"
  PROCESSED=$((PROCESSED+1))

  # Determine status
  STATUS="PARTIAL"
  if   echo "$RESULT" | grep -qiE '^[[:space:]*#]*STATUS:[[:space:]]*\**DONE';    then STATUS="DONE"
  elif echo "$RESULT" | grep -qiE '^[[:space:]*#]*STATUS:[[:space:]]*\**BLOCKED'; then STATUS="BLOCKED"
  elif [ "$IS_ERR" = "true" ] || [ -z "$RESULT" ]; then
    if echo "$RESULT" | grep -qiE 'limit|rate|429|overloaded|resets'; then STATUS="LIMIT"
    else STATUS="ERROR"; fi
  fi
  [ "$RC" -eq 143 ] && STATUS="TIMEOUT"

  EXTRA="$(printf '%s' "$USAGE_JSON" | python3 -c 'import json,sys; u=json.load(sys.stdin); u["cost_est"]=float(sys.argv[1] or 0); print(json.dumps(u))' "$COST_EST" 2>/dev/null || echo '{}')"
  log_event "task_end" "$LANE" "$NAME" "$STATUS" "$MODEL" "$COST" "$TOKENS_EST" "$TOKENS_ACTUAL" "attempt $ATT, ${ELAPSED}s, exit $RC" "$EXTRA"
  [ "$STATUS" = "DONE" ] || [ "$STATUS" = "PARTIAL" ] && python3 "$ORBIT_HOME/system/estimate.py" record --task "$NAME" --model "$MODEL" --predicted "$COST_EST" --actual "$COST" >/dev/null 2>&1 || true

  FIRE_SUMMARY="$FIRE_SUMMARY $NAME:$STATUS"

  case "$STATUS" in
    DONE|BLOCKED)
      { echo; echo "---"; echo "## Agent report $STAMP"; echo "$RESULT"; } >> "$TASK_FILE"
      if [ "$STATUS" = "DONE" ]; then mv "$TASK_FILE" "$DONE/"; else mv "$TASK_FILE" "$BLOCKED/"; fi
      rm -f "$STATE/$NAME.session" "$STATE/$NAME.attempts"
      ;;
    LIMIT)
      mv "$TASK_FILE" "$Q/"
      ATT=$((ATT-1)); echo "$ATT" > "$STATE/$NAME.attempts"
      log_event "fire_limit" "" "" "stopped" "" 0 0 0 "usage limit hit, remaining tasks deferred"
      STOP=1; STOP_FIRE=1
      ;;
    ERROR)
      mv "$TASK_FILE" "$Q/"
      rm -f "$STATE/$NAME.session"
      ;;
    *)
      mv "$TASK_FILE" "$Q/"
      ;;
  esac
done
  # Backlog: with budget and time left and nothing runnable in the queue, pull the next one-shot task.
  [ "$STOP_FIRE" -eq 1 ] && break
  [ "$STOP" -eq 1 ] && break
  [ -n "${ORBIT_MANUAL:-}" ] && break
  [ "$PROCESSED" -ge "$MAX_TASKS_PER_RUN" ] && break
  # One pass over the queue per fire; only a backlog pull earns another pass (bounded by backlog_pulls_per_fire).
  NEXT_BACKLOG="$(ls "$ORBIT_HOME"/backlog/[0-9]*.md 2>/dev/null | sort | head -1)"
  MAXPULL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("backlog_pulls_per_fire",3))' "$ORBIT_HOME/config/schedule.json" 2>/dev/null || echo 3)"
  if [ -n "$NEXT_BACKLOG" ] && [ "$PULLS" -lt "$MAXPULL" ]; then
    mv "$NEXT_BACKLOG" "$Q/"; PULLS=$((PULLS+1)); PENDING=$((PENDING+1))
    log_event "backlog_pull" "" "$(basename "$NEXT_BACKLOG" .md)" "queued" "" 0 0 0 "pulled from backlog ($PULLS of $MAXPULL this fire)"
    continue
  fi
  break
done

# Count remaining
LEFT=0
for f in "$Q"/*.md; do
  [ -e "$f" ] || break
  case "$(basename "$f")" in _*) ;; *) LEFT=$((LEFT+1));; esac
done

log_event "fire_end" "" "" "done" "" "$FIRE_COST_TOTAL" 0 0 "$PROCESSED tasks, $LEFT remaining, cost \$$FIRE_COST_TOTAL"
notify "$PROCESSED task(s):$FIRE_SUMMARY" "est. cost \$$FIRE_COST_TOTAL · $LEFT left"
