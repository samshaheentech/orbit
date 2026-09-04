#!/usr/bin/env python3
"""
The 22:00 fire: draft tomorrow's plan from the queue, the last 24h of events, and Sam's plan.md.
  python3 lanes/system/plan.py [--now ISO] [--dry-run] [--force]
Emits one plan_draft. Never clears plan.md (brief.py does that at 02:00).
"""
import argparse, datetime as dt, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SLOT = 22
TASK = "200-system-plan"


def gather(now):
    q = []
    for p in sorted((C.HOME / "queue").glob("*.md")):
        if p.name.startswith("_"):
            continue
        fm, title = C.frontmatter(p)
        heavy = fm.get("weight") == "heavy" or "fable" in fm.get("model", "") or "resume" in p.stem or "digest" in p.stem
        q.append({"task": p.stem, "title": title, "lane": fm.get("lane", "general"), "model": fm.get("model", ""),
                  "days": fm.get("days", ""), "hours": fm.get("hours", ""), "heavy": bool(heavy)})
    since = now - dt.timedelta(hours=24)
    ev = [e for e in C.read_events() if C.ts(e) >= since]
    ran = [{"task": e["task"], "status": e["status"]} for e in ev if e.get("type") == "task_end"]
    blocked = [{"task": e["task"], "why": e.get("note", "")} for e in ev
               if e.get("type") == "task_blocked" or (e.get("type") == "task_end" and e.get("status") == "BLOCKED")]
    acts = {}
    for e in ev:
        if e.get("type") == "item_action":
            acts[e.get("action")] = acts.get(e.get("action"), 0) + 1
    limit = any(e.get("type") == "fire_limit" for e in ev)
    sam = C.PLAN.read_text(encoding="utf-8").strip() if C.PLAN.exists() else ""
    win = {}
    try:
        sys.path.insert(0, str(C.HOME / "system")); import window as W
        win = W.status(now)
    except Exception: pass
    return {"queue": q, "ran": ran, "blocked": blocked, "actions": acts, "limit_hit": limit, "sam_input": sam, "window": win}


def fallback(g, tomorrow):
    lines = ["Plan for %s (drafted without the model)" % tomorrow.strftime("%A %b %d")]
    if g["sam_input"]:
        lines.append("First: your input. " + g["sam_input"].splitlines()[0][:140])
    light = [t for t in g["queue"] if not t["heavy"]]
    heavy = [t for t in g["queue"] if t["heavy"]]
    lines.append("Tonight, light first: " + (", ".join(t["task"] for t in light) or "none"))
    lines.append("Then heavy: " + (", ".join(t["task"] for t in heavy) or "none"))
    lines.append("Budget left goes to the backlog; brief at 07:40.")
    if g["blocked"]:
        lines.append("Blocked and waiting on you: " + ", ".join(b["task"] for b in g["blocked"]))
    if g["limit_hit"]:
        lines.append("A usage limit was hit today; tomorrow runs light until the window is confirmed.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    now = C.parse_now(a.now)
    if not a.force and not C.in_band(now, C.sched()["plan_at"]):
        C.requeue(TASK)
        C.status("DONE", "nothing", "hour gate", "not my hour (%s), slot is %02d:00" % (now.strftime("%H:%M"), SLOT), "run at %02d:00" % SLOT)
        return
    tomorrow = (now + dt.timedelta(days=1)).date()
    g = gather(now)
    prompt = (
        "You are Orbit's planner, drafting tonight's plan for Sam. Orbit works two windows it owns, 22:00 to 03:00 and 03:00 to 08:00, "
        "polling every 15 minutes and draining a budget of about half a window each; light tasks run first, heavy ones (Fable, the resume loop, "
        "digests, grading) after, and the morning brief lands at 07:40. Order the queue for tonight and say what the backlog should add if budget is left. "
        "Anything in sam_input comes first and is quoted back. Blocked tasks are listed as waiting "
        "on Sam, not scheduled. Under 20 lines, plain text, no markdown headers, no em-dashes. "
        "Return strict JSON only: {\"body\": \"...\"}.\n\nDATA:\n" + json.dumps(g, ensure_ascii=False))
    fixture = str(Path(__file__).parent / "fixtures" / "plan.json") if a.dry_run else None
    out, cost = C.call_claude(prompt, "claude-sonnet-5", fixture=fixture)
    body = out.get("body") if isinstance(out, dict) else None
    used_model = bool(body)
    if not body:
        body = fallback(g, dt.datetime.combine(tomorrow, dt.time()))
    ok = C.emit("plan", "--text", body, "--date", tomorrow.isoformat())
    C.requeue(TASK)
    C.status("DONE" if ok else "PARTIAL",
             "emitted plan_draft for %s" % tomorrow.isoformat(),
             "emit.py returned %s; %d queued tasks, %d ran today, %d blocked" % (ok, len(g["queue"]), len(g["ran"]), len(g["blocked"])),
             ("model prose" if used_model else "fallback prose") + ("; Sam left input" if g["sam_input"] else ""),
             "brief.py at 02:00 reads this draft", cost)


if __name__ == "__main__":
    main()
