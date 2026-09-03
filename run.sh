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
  # log_event <type> <lane> <task> <status> <model> <cost> <tokens_est> <tokens_actual> <note>
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '{"ts":"%s","fire":"%s","type":"%s","lane":"%s","task":"%s","status":"%s","model":"%s","cost_usd":%s,"tokens_est":%s,"tokens_actual":%s,"note":%s}\n' \
    "$ts" "$FIRE_ID" "$1" "$2" "$3" "$4" "$5" "${6:-0}" "${7:-0}" "${8:-0}" "$(printf '%s' "${9:-}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')" \
    >> "$EVENTS"
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
  # Map friendly model names to claude CLI model strings
  case "$1" in
    fable*|fable-5-1)   echo "claude-fable-5-1" ;;
    sonnet-5|sonnet5)   echo "claude-sonnet-5" ;;
    haiku*)             echo "claude-haiku-4-5-20251001" ;;
    *)                  echo "$DEFAULT_MODEL" ;;
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
  kill "$wd" 2>/dev/null; wait "$wd" 2>/dev/null
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

log_event "fire_start" "" "" "running" "" 0 0 0 ""

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
for TASK_FILE in "$Q"/*.md; do
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
  if git -C "$DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
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
  PROMPT="User config: $CONFIG
Task file: $TASK_FILE
Working tree: $WT  Branch: $BRANCH
Allowed tools: $TOOLS

${CONT}$(cat "$TASK_FILE")"

  # Estimate tokens (rough: ~3 tokens/char of prompt)
  PROMPT_CHARS="${#PROMPT}"
  TOKENS_EST=$(( PROMPT_CHARS * 3 / 4 ))

  log_event "task_start" "$LANE" "$NAME" "running" "$MODEL" 0 "$TOKENS_EST" 0 "attempt $ATT"

  START_SEC=$(date +%s)
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

  log_event "task_end" "$LANE" "$NAME" "$STATUS" "$MODEL" "$COST" "$TOKENS_EST" 0 "attempt $ATT, ${ELAPSED}s, exit $RC"

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
      STOP=1
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

# Count remaining
LEFT=0
for f in "$Q"/*.md; do
  [ -e "$f" ] || break
  case "$(basename "$f")" in _*) ;; *) LEFT=$((LEFT+1));; esac
done

log_event "fire_end" "" "" "done" "" "$FIRE_COST_TOTAL" 0 0 "$PROCESSED tasks, $LEFT remaining, cost \$$FIRE_COST_TOTAL"
notify "$PROCESSED task(s):$FIRE_SUMMARY" "est. cost \$$FIRE_COST_TOTAL · $LEFT left"
