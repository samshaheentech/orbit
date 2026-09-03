#!/usr/bin/env python3
"""
orbit/system/emit.py — append a well-formed event to briefs/data/events.jsonl

  emit.py item   --kind lead --id <id> --title "..." [--body "..."] [--meta '{...}'] [--lane career]
  emit.py update --id <id> --patch '{"meta":{"score":88}}'
  emit.py brief  --file brief.json | --json '{...}'
  emit.py plan   --file plan.md    | --text "..."   [--date yyyy-mm-dd]
  emit.py event  --type <type> [--json '{...}']

ts is added here. fire and lane default to $ORBIT_FIRE and $ORBIT_LANE, which run.sh exports.
"""
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parent.parent))
EVENTS = ROOT / "briefs" / "data" / "events.jsonl"


def write(ev: dict):
    ev = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          "fire": os.environ.get("ORBIT_FIRE", ""), **ev}
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS, "a") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "type": ev["type"], "id": ev.get("id", "")}))


def load_json(s: str, what: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        sys.exit(f"{what} is not valid JSON: {e}")


def main():
    p = argparse.ArgumentParser(prog="emit.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("item")
    a.add_argument("--kind", required=True); a.add_argument("--id", required=True)
    a.add_argument("--title", required=True); a.add_argument("--body", default="")
    a.add_argument("--meta", default="{}"); a.add_argument("--lane", default=os.environ.get("ORBIT_LANE", "general"))

    u = sub.add_parser("update")
    u.add_argument("--id", required=True); u.add_argument("--patch", required=True)

    b = sub.add_parser("brief")
    b.add_argument("--file"); b.add_argument("--json")

    pl = sub.add_parser("plan")
    pl.add_argument("--file"); pl.add_argument("--text"); pl.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))

    ev = sub.add_parser("event")
    ev.add_argument("--type", required=True); ev.add_argument("--json", default="{}")

    n = p.parse_args()

    if n.cmd == "item":
        if len(n.title) > 90 or len(n.body) > 300:
            sys.exit("title max 90 chars, body max 300; put the long version in briefs/data/items/<id>.md and set meta.path")
        write({"type": "item", "lane": n.lane, "kind": n.kind, "id": n.id, "title": n.title,
               "body": n.body, "meta": load_json(n.meta, "--meta")})
    elif n.cmd == "update":
        write({"type": "item_update", "id": n.id, "patch": load_json(n.patch, "--patch")})
    elif n.cmd == "brief":
        raw = Path(n.file).read_text() if n.file else n.json
        if not raw: sys.exit("brief needs --file or --json")
        d = load_json(raw, "brief")
        for k in ("date", "accomplished", "to_read", "questions", "tomorrow"):
            d.setdefault(k, [] if k != "date" else datetime.now().strftime("%Y-%m-%d"))
        write({"type": "brief", **d})
    elif n.cmd == "plan":
        body = Path(n.file).read_text() if n.file else (n.text or "")
        if not body.strip(): sys.exit("plan needs --file or --text")
        write({"type": "plan_draft", "date": n.date, "body": body})
    elif n.cmd == "event":
        write({"type": n.type, **load_json(n.json, "--json")})


if __name__ == "__main__":
    main()
