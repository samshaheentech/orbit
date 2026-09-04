#!/usr/bin/env python3
"""
The 02:00 fire: build the morning brief from everything since the last brief, then archive Sam's plan.md.
  python3 lanes/system/brief.py [--now ISO] [--dry-run] [--force]
Runs first in the queue (filename 210-) so it reports on yesterday before today's lane tasks start.
"""
import argparse, datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SLOT = 2
TASK = "210-system-brief"


def report_lines(folder, task, keys=("Changed", "Notes", "Next")):
    p = C.HOME / folder / (task + ".md")
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            for k in keys:
                if line.startswith(k + ":"):
                    out[k] = line.split(":", 1)[1].strip()
    return out


def usage_block(recent, ev, now):
    by_lane, by_model = {}, {}
    ratios = []
    for e in recent:
        if e.get("type") == "task_end":
            c = float(e.get("cost_usd") or 0)
            by_lane[e.get("lane") or "general"] = round(by_lane.get(e.get("lane") or "general", 0) + c, 2)
            m = e.get("model", ""); m = "Fable 5.1" if "fable" in m else "Sonnet 5" if "sonnet" in m else "Haiku 4.5" if "haiku" in m else (m or "unknown")
            by_model[m] = round(by_model.get(m, 0) + c, 2)
            if float(e.get("cost_est") or 0) > 0 and c > 0: ratios.append(c / float(e["cost_est"]))
    headroom = None
    try:
        sys.path.insert(0, str(C.HOME / "system")); import window as W
        headroom = W.status(now).get("minutes_left")
    except Exception: pass
    return {"spend_by_lane": by_lane, "spend_by_model": by_model,
            "est_ratio": round(sum(ratios) / len(ratios), 2) if ratios else None,
            "headroom_min": headroom, "limit_hit": any(e.get("type") == "fire_limit" for e in recent)}


def gather(now):
    ev = C.read_events()
    last = None
    for e in ev:
        if e.get("type") == "brief":
            last = C.ts(e)
    recent = [e for e in ev if last is None or C.ts(e) > last]
    accomplished = []
    for e in recent:
        if e.get("type") == "task_end" and e.get("status") == "DONE":
            r = report_lines("done", e["task"])
            accomplished.append("%s: %s" % (e["task"], r.get("Changed") or "done"))
    acted = {e["id"] for e in ev if e.get("type") == "item_action" and e.get("id")}
    fresh = [e for e in recent if e.get("type") == "item" and e.get("id") not in acted and e.get("kind") != "profile"]
    seen, to_read = set(), []
    for e in reversed(fresh):
        if e["id"] in seen:
            continue
        seen.add(e["id"]); to_read.append({"id": e["id"], "title": e.get("title", e["id"])})
        if len(to_read) >= 12:
            break
    questions = []
    for e in recent:
        if e.get("type") == "item" and isinstance(e.get("meta"), dict) and e["meta"].get("question"):
            questions.append("%s: %s" % (e.get("title", e["id"]), e["meta"]["question"]))
    for e in recent:
        if e.get("type") == "task_blocked" or (e.get("type") == "task_end" and e.get("status") == "BLOCKED"):
            r = report_lines("blocked", e["task"])
            questions.append("%s is blocked: %s" % (e["task"], r.get("Next") or e.get("note", "see blocked/")))
    plan = None
    for e in ev:
        if e.get("type") == "plan_draft":
            plan = e
    tomorrow = [l.strip(" -*") for l in (plan or {}).get("body", "").splitlines() if l.strip()][:8]
    cost = sum(float(e.get("cost_usd") or 0) for e in recent if e.get("type") == "fire_end")
    usage = usage_block(recent, ev, now)
    return {"date": now.date().isoformat(), "accomplished": accomplished, "to_read": to_read, "usage": usage,
            "questions": questions, "tomorrow": tomorrow, "cost_since_last": round(cost, 2),
            "fires_since_last": sum(1 for e in recent if e.get("type") == "fire_end")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    now = C.parse_now(a.now)
    if not a.force and not C.in_band(now, C.sched()["brief_at"]):
        C.requeue(TASK)
        C.status("DONE", "nothing", "hour gate", "not my hour (%s), slot is %02d:00" % (now.strftime("%H:%M"), SLOT), "run at %02d:00" % SLOT)
        return
    g = gather(now)
    prompt = (
        "You are writing Sam's morning brief for Orbit. Turn the raw lists below into tight lines, at most 12 words each, "
        "plain text, no em-dashes, no markdown. Drop nothing that is a question. If accomplished is empty say so in one line. "
        "Return strict JSON only with keys date, accomplished, questions, tomorrow.\n\nDATA:\n" + json.dumps(g, ensure_ascii=False))
    fixture = str(Path(__file__).parent / "fixtures" / "brief.json") if a.dry_run else None
    out, cost = C.call_claude(prompt, "claude-sonnet-5", fixture=fixture)
    brief = {k: g[k] for k in ("date", "accomplished", "to_read", "questions", "tomorrow", "usage")}
    used_model = False
    if isinstance(out, dict) and all(k in out for k in ("accomplished", "questions", "tomorrow")):
        brief.update({"accomplished": list(out["accomplished"]), "questions": list(out["questions"]), "tomorrow": list(out["tomorrow"])})
        used_model = True
    ok = C.emit("brief", "--json", json.dumps(brief, ensure_ascii=False))
    consumed = ""
    if C.PLAN.exists() and C.PLAN.read_text(encoding="utf-8").strip():
        body = C.PLAN.read_text(encoding="utf-8")
        C.emit("event", "--type", "plan_consumed", "--json", json.dumps({"body": body}, ensure_ascii=False))
        C.PLAN.write_text("", encoding="utf-8")
        consumed = "; archived and cleared plan.md (%d chars)" % len(body)
    C.requeue(TASK)
    C.status("DONE" if ok else "PARTIAL",
             "emitted brief for %s%s" % (g["date"], consumed),
             "%d accomplished, %d to read, %d questions, %d tomorrow lines; %d fires, $%.2f since last brief" % (
                 len(brief["accomplished"]), len(brief["to_read"]), len(brief["questions"]), len(brief["tomorrow"]),
                 g["fires_since_last"], g["cost_since_last"]),
             "model prose" if used_model else "raw lists (model call failed or dry run)",
             "lane tasks run next in this fire", cost)


if __name__ == "__main__":
    main()
