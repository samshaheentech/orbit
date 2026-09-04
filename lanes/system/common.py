#!/usr/bin/env python3
"""Shared helpers for Orbit system scripts (plan.py, brief.py, retro.py). Stdlib only."""
import datetime as dt, json, os, re, subprocess, sys
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[2]))
EVENTS = HOME / "briefs" / "data" / "events.jsonl"
PLAN = HOME / "briefs" / "data" / "plan.md"
EMIT = HOME / "system" / "emit.py"
def sched():
    p = HOME / "config" / "schedule.json"
    d = {"windows": [22, 3], "window_hours": 5, "plan_at": "22:00", "brief_at": "07:40"}
    if p.exists():
        d.update(json.loads(p.read_text(encoding="utf-8")))
    return d


def hm(s):
    h, m = s.split(":"); return int(h), int(m)


def in_band(now, hhmm, after_min=25):
    """True if now is within after_min minutes after hh:mm (the poll after a target time)."""
    h, m = hm(hhmm)
    for day in (-1, 0):
        t = (now + dt.timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0)
        if 0 <= (now - t).total_seconds() / 60 <= after_min:
            return True
    return False


def parse_now(s):
    if not s:
        return dt.datetime.now()
    return dt.datetime.fromisoformat(s)


def in_slot(now, hour, window_min=30):
    """True if now is within window_min minutes of hour:00 (wrap-safe)."""
    best = 10**9
    for day in (-1, 0, 1):
        slot = (now + dt.timedelta(days=day)).replace(hour=hour, minute=0, second=0, microsecond=0)
        best = min(best, abs((now - slot).total_seconds()) / 60)
    return best <= window_min


def read_events():
    if not EVENTS.exists():
        return []
    out = []
    for line in EVENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def ts(e):
    try:
        return dt.datetime.strptime(e.get("ts", "")[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return dt.datetime.min


def frontmatter(path):
    text = Path(path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = re.sub(r"\s+#.*$", "", v).strip()
    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip(); break
    return fm, title


def strip_fences(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s


def call_claude(prompt, model, fixture=None, timeout=300):
    """Run claude -p and return (parsed_json_or_None, cost_usd). fixture: a JSON file used instead."""
    if fixture:
        return json.loads(Path(fixture).read_text(encoding="utf-8")), 0.0
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
           "--permission-mode", "dontAsk", "--tools", "", "--max-turns", "1"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        data = json.loads(r.stdout or "{}")
        cost = float(data.get("total_cost_usd") or 0)
        if data.get("is_error"):
            return None, cost
        return json.loads(strip_fences(str(data.get("result", "")))), cost
    except Exception as e:  # noqa: BLE001 - any failure means fallback
        sys.stderr.write("claude call failed: %s\n" % e)
        return None, 0.0


def emit(*args):
    r = subprocess.run([sys.executable, str(EMIT), *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.returncode == 0


def requeue(task_name):
    src = HOME / "running" / (task_name + ".md")
    if not src.exists():
        return False
    text = src.read_text(encoding="utf-8")
    cut = text.find("\n---\n## Agent report")
    if cut != -1:
        text = text[:cut].rstrip() + "\n"
    (HOME / "queue").mkdir(exist_ok=True)
    (HOME / "queue" / (task_name + ".md")).write_text(text, encoding="utf-8")
    return True


def status(kind, changed, verified, notes, nxt, cost=0.0):
    print("COST_USD: %.4f" % cost)
    print("STATUS: %s" % kind)
    print("Changed: %s" % (changed or "nothing"))
    print("Verified: %s" % (verified or "not run"))
    print("Notes: %s" % (notes or ""))
    print("Next: %s" % (nxt or "nothing"))
