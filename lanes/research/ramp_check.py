#!/usr/bin/env python3
"""
Check open ramp problems: run each problem's tests, update meta.json and the log.
  python3 lanes/research/ramp_check.py [--now ISO] [--json]
No model calls. Prints a JSON summary; the ramp task reads it to decide what to create next.
"""
import argparse, datetime as dt, json, os, subprocess, sys
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[2]))
RAMP = HOME / "ramp"
EMIT = HOME / "system" / "emit.py"


def emit_update(pid, patch):
    subprocess.run([sys.executable, str(EMIT), "update", "--id", pid, "--patch", json.dumps(patch)], capture_output=True, text=True)


def run_tests(d):
    tests = sorted(d.glob("test_*.py"))
    if not tests:
        return None, "no tests"
    try:
        r = subprocess.run([sys.executable, str(tests[0])], cwd=str(d), capture_output=True, text=True, timeout=60)
        return r.returncode == 0, (r.stdout + r.stderr)[-400:]
    except subprocess.TimeoutExpired:
        return False, "timeout"


def solution_touched(d):
    s = d / "solution.py"
    if not s.exists():
        return False
    body = s.read_text(encoding="utf-8")
    after_def = body.split("def ", 1)[-1] if "def " in body else ""
    return not any(line.strip() == "pass" for line in after_def.splitlines()[1:3])


def load_meta(d):
    mp = d / "meta.json"
    return (json.loads(mp.read_text(encoding="utf-8")), mp) if mp.exists() else (None, mp)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--now"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()
    today = now.date()
    summary = {"open": [], "untouched": [], "passed": [], "struggled": [], "returned": [], "open_count": 0}
    if not RAMP.exists():
        print(json.dumps(summary)); return
    for d in sorted(p for p in RAMP.iterdir() if p.is_dir()):
        m, mp = load_meta(d)
        if not m:
            continue
        st = m.get("status", "open")
        if st == "passed" and m.get("return") and dt.date.fromisoformat(m["return"]) <= today:
            m["status"] = "open"; m["due"] = (today + dt.timedelta(days=2)).isoformat(); m["retention"] = True
            sol = d / "solution.py"
            if sol.exists():
                (d / "solution.passed.py").write_text(sol.read_text(encoding="utf-8"), encoding="utf-8")
                sol.write_text(m.get("signature", "def solve(*args):\n    pass\n"), encoding="utf-8")
            emit_update(m["id"], {"meta": {"status": "open", "due": m["due"], "retention": True}})
            summary["returned"].append(m["slug"]); st = "open"
        if st in ("open", "struggled"):
            ok, out = run_tests(d)
            if ok:
                m["status"] = "passed"; m["passed"] = today.isoformat(); m["return"] = (today + dt.timedelta(days=7)).isoformat()
                emit_update(m["id"], {"meta": {"status": "passed", "return": m["return"]}})
                summary["passed"].append(m["slug"])
            else:
                due = dt.date.fromisoformat(m.get("due", today.isoformat()))
                if due < today:
                    m["status"] = "struggled"; m["hints"] = int(m.get("hints", 0)); m["due"] = (today + dt.timedelta(days=2)).isoformat()
                    emit_update(m["id"], {"meta": {"status": "struggled", "due": m["due"]}})
                    summary["struggled"].append({"slug": m["slug"], "hints": m["hints"], "last": out.strip()[-160:]})
                else:
                    (summary["open"] if solution_touched(d) else summary["untouched"]).append(m["slug"])
        mp.write_text(json.dumps(m, indent=1), encoding="utf-8")
        if m.get("status") in ("open", "struggled"):
            summary["open_count"] += 1
    print(json.dumps(summary, indent=None if a.json else 1))


if __name__ == "__main__":
    main()
