#!/usr/bin/env python3
"""
Windows, budget, calibration, sessions. The runner asks `decide` every poll.

  window.py decide  [--now ISO]  -> {"mode":"fire|idle","starts_window":bool,"window_start":..,"reset_at":..,
                                     "deadline":..,"spent_usd":..,"budget_usd":..,"budget_left_usd":..,"reason":".."}
  window.py status  [--now ISO]  -> the same plus sessions this week, calibration, last window spend (also written to
                                     state/system/window.json and briefs/data/window.json for the webapp)
  window.py calibrate [--now ISO] -> recompute usd_per_pct from meter_reading and fire_limit events

Orbit owns the windows listed in config/schedule.json (hours). A window starts at the first fire at or after its hour and
resets window_hours later. The budget is budget_pct of a window, converted with usd_per_pct learned from:
  - meter_reading events (the user types the meter % into the webapp during an Orbit window; Sam is asleep, so the
    reading is Orbit's spend), and
  - fire_limit events inside an Orbit window (spend at the limit is ~100%).
No API exposes usage; this is the best signal there is, and it gets better with each reading.
"""
import argparse, datetime as dt, json, os, statistics
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[1]))
EVENTS = HOME / "briefs" / "data" / "events.jsonl"
SCHED = HOME / "config" / "schedule.json"
STATE = HOME / "state" / "system" / "window.json"
PUB = HOME / "briefs" / "data" / "window.json"
CAL = HOME / "state" / "system" / "calibration.json"


def sched():
    d = {"windows": [22, 3], "window_hours": 5, "budget_pct": 50, "weekly_sessions_max": 14, "default_usd_per_pct": 0.08, "brief_at": "07:40"}
    if SCHED.exists():
        d.update(json.loads(SCHED.read_text(encoding="utf-8")))
    return d


def events():
    if not EVENTS.exists(): return []
    out = []
    for l in EVENTS.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(l))
        except ValueError: pass
    return out


def ts(e):
    return dt.datetime.strptime(e["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)


def current_slot(now, s):
    """The Orbit window slot containing now: (slot_start, slot_end) or None. Slots are [hour, hour+window_hours)."""
    for h in s["windows"]:
        for day in (-1, 0):
            start = (now + dt.timedelta(days=day)).replace(hour=h, minute=0, second=0, microsecond=0)
            end = start + dt.timedelta(hours=s["window_hours"])
            if start <= now < end:
                return start, end
    return None


def window_starts(ev):
    return [e for e in ev if e.get("type") == "window_start"]


def calibration(ev, s):
    """usd_per_pct from meter readings and limit hits inside Orbit windows."""
    samples = []
    ws = window_starts(ev)
    def spend_between(a, b):
        return sum(float(e.get("cost_usd") or 0) for e in ev if e.get("type") == "task_end" and a <= ts(e) <= b)
    for e in ev:
        if e.get("type") == "meter_reading" and e.get("pct"):
            t = ts(e); pct = float(e["pct"])
            w = [x for x in ws if ts(x) <= t and t < ts(x) + dt.timedelta(hours=s["window_hours"])]
            if w and pct > 0:
                sp = spend_between(ts(w[-1]), t)
                if sp > 0: samples.append({"ts": e["ts"], "usd_per_pct": sp / pct, "source": "meter"})
        elif e.get("type") == "fire_limit":
            t = ts(e)
            w = [x for x in ws if ts(x) <= t and t < ts(x) + dt.timedelta(hours=s["window_hours"])]
            if w:
                sp = spend_between(ts(w[-1]), t)
                if sp > 0: samples.append({"ts": e["ts"], "usd_per_pct": sp / 100.0, "source": "limit"})
    recent = samples[-5:]
    val = statistics.median(x["usd_per_pct"] for x in recent) if recent else s["default_usd_per_pct"]
    out = {"usd_per_pct": round(val, 4), "samples": len(samples), "basis": "measured" if recent else "default"}
    CAL.parent.mkdir(parents=True, exist_ok=True); CAL.write_text(json.dumps({**out, "recent": recent}, indent=1), encoding="utf-8")
    return out


def decide(now):
    s = sched(); ev = events()
    cal = calibration(ev, s)
    slot = current_slot(now, s)
    week_start = (now - dt.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    sessions = [e for e in window_starts(ev) if ts(e) >= week_start]
    base = {"now": now.isoformat(timespec="minutes"), "usd_per_pct": cal["usd_per_pct"], "calibration": cal["basis"],
            "sessions_this_week": len(sessions), "weekly_sessions_max": s["weekly_sessions_max"]}
    if not slot:
        return {**base, "mode": "idle", "starts_window": False, "reason": "outside Orbit's windows"}
    slot_start, slot_end = slot
    started = [e for e in window_starts(ev) if slot_start <= ts(e) < slot_end]
    starts = not started
    if starts and len(sessions) >= s["weekly_sessions_max"]:
        return {**base, "mode": "idle", "starts_window": False, "reason": "weekly session budget used"}
    window_start = ts(started[0]) if started else now
    reset_at = window_start + dt.timedelta(hours=s["window_hours"])
    deadline = min(reset_at, slot_end) - dt.timedelta(minutes=5)
    spent = sum(float(e.get("cost_usd") or 0) for e in ev if e.get("type") == "task_end" and window_start <= ts(e) <= now)
    budget = round(s["budget_pct"] * cal["usd_per_pct"], 4)
    limit_hit = any(e.get("type") == "fire_limit" and window_start <= ts(e) <= now for e in ev)
    out = {**base, "starts_window": starts, "window_start": window_start.isoformat(timespec="minutes"), "reset_at": reset_at.isoformat(timespec="minutes"),
           "deadline": deadline.isoformat(timespec="minutes"), "deadline_epoch": int(deadline.timestamp()),
           "spent_usd": round(spent, 4), "budget_usd": budget, "budget_left_usd": round(max(budget - spent, 0), 4), "limit_hit": limit_hit}
    if limit_hit:
        return {**out, "mode": "idle", "reason": "limit already hit in this window"}
    if now >= deadline:
        return {**out, "mode": "idle", "reason": "past the window deadline"}
    if spent >= budget:
        return {**out, "mode": "idle", "reason": "window budget spent"}
    return {**out, "mode": "fire", "reason": "in window with budget and time"}


def status(now):
    s = sched(); ev = events()
    d = decide(now)
    since = now - dt.timedelta(hours=s["window_hours"])
    spend = {}
    for e in ev:
        if e.get("type") == "task_end" and ts(e) > since:
            k = e.get("lane") or "general"; spend[k] = round(spend.get(k, 0) + float(e.get("cost_usd") or 0), 4)
    nxt = None
    for h in sorted(s["windows"]):
        cand = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if cand > now: nxt = cand; break
    if nxt is None:
        nxt = (now + dt.timedelta(days=1)).replace(hour=min(s["windows"]), minute=0, second=0, microsecond=0)
    out = {**d, "synced": d.get("mode") != "idle" or "reset_at" in d, "minutes_left": (int((dt.datetime.fromisoformat(d["reset_at"]) - now).total_seconds() // 60) if "reset_at" in d else None),
           "last_window_spend": spend, "next_window": nxt.isoformat(timespec="minutes"), "budget_pct": s["budget_pct"], "windows": s["windows"], "brief_at": s["brief_at"]}
    for p in (STATE, PUB):
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    for c in ("decide", "status", "calibrate"):
        sub.add_parser(c).add_argument("--now")
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now) if getattr(a, "now", None) else dt.datetime.now()
    if a.cmd == "decide": print(json.dumps(decide(now)))
    elif a.cmd == "calibrate": print(json.dumps(calibration(events(), sched())))
    else: print(json.dumps(status(now), indent=1))


if __name__ == "__main__":
    main()
