#!/usr/bin/env python3
"""
Deletion proposals with a 14-day gate.

  deletions.py plan     [--now ISO] [--emit]   -> {"propose":[...], "execute":[...]}
  deletions.py executed --id <item id> --count N [--now ISO]

propose: senders with action propose_delete or archive-only noise with >= MIN_COUNT messages and no proposal yet (cap 10).
execute: deletion items with an approve action at least 14 days old, no skip after it, not yet executed.
"""
import argparse, datetime as dt, json, os, subprocess, sys
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[2]))
SENDERS = HOME / "config" / "lanes" / "operations" / "senders.json"
EVENTS = HOME / "briefs" / "data" / "events.jsonl"
EMIT = HOME / "system" / "emit.py"
GATE_DAYS, CAP, MIN_COUNT = 14, 10, 5


def events():
    if not EVENTS.exists(): return []
    out = []
    for l in EVENTS.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(l))
        except ValueError: pass
    return out


def ts(e):
    return dt.datetime.strptime(e.get("ts", "")[:19], "%Y-%m-%dT%H:%M:%S")


def emit(*args):
    return subprocess.run([sys.executable, str(EMIT), *args], capture_output=True, text=True).returncode == 0


def plan(now, do_emit):
    ev = events()
    items, acts = {}, {}
    for e in ev:
        if e.get("type") == "item" and e.get("kind") == "deletion": items[e["id"]] = dict(e)
        elif e.get("type") == "item_update" and e.get("id") in items: items[e["id"]].setdefault("meta", {}).update((e.get("patch") or {}).get("meta", {}))
        elif e.get("type") == "item_action" and e.get("id") in items: acts.setdefault(e["id"], []).append(e)
    proposed = {(i.get("meta", {}).get("sender"), i.get("meta", {}).get("account")) for i in items.values()}
    senders = json.loads(SENDERS.read_text(encoding="utf-8"))["senders"] if SENDERS.exists() else []
    propose = []
    for s in senders:
        eligible = s.get("action") == "propose_delete" or (s.get("action") == "archive" and s.get("label") == "orbit/noise" and int(s.get("count", 0)) >= MIN_COUNT)
        if eligible and (s["sender"], s["account"]) not in proposed and len(propose) < CAP:
            propose.append({"id": "deletion-%s-%s" % (s["account"], s["sender"].replace("@", "-at-").replace(".", "-")),
                            "sender": s["sender"], "account": s["account"], "count": int(s.get("count", 0)), "label": s.get("label", "")})
    execute = []
    for iid, it in items.items():
        if it.get("meta", {}).get("executed"): continue
        last = None
        for a in sorted(acts.get(iid, []), key=ts):
            if a.get("action") in ("approve", "skip"): last = a
        if last and last["action"] == "approve" and (now - ts(last)).days >= GATE_DAYS:
            execute.append({"id": iid, "sender": it["meta"].get("sender"), "account": it["meta"].get("account"), "approved": last["ts"], "age_days": (now - ts(last)).days})
    if do_emit:
        for p in propose:
            emit("item", "--kind", "deletion", "--id", p["id"], "--lane", "operations",
                 "--title", "%s, %d messages" % (p["sender"], p["count"]),
                 "--body", "All %s in %s. Approve to trash everything from this sender 14 days from now; skip to keep." % (p["label"] or "noise", p["account"]),
                 "--meta", json.dumps({"sender": p["sender"], "count": p["count"], "account": p["account"], "proposed": now.date().isoformat()}))
    return {"propose": propose, "execute": execute}


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("plan"); p.add_argument("--emit", action="store_true"); p.add_argument("--now")
    x = sub.add_parser("executed"); x.add_argument("--id", required=True); x.add_argument("--count", type=int, required=True); x.add_argument("--now")
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    if a.cmd == "plan":
        print(json.dumps(plan(now, a.emit), indent=1))
    elif a.cmd == "executed":
        ok = emit("update", "--id", a.id, "--patch", json.dumps({"meta": {"executed": now.date().isoformat(), "trashed": a.count}}))
        print(json.dumps({"ok": ok}))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
