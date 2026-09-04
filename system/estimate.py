#!/usr/bin/env python3
"""
Cost estimator for a task, from Orbit's own history.
  estimate.py predict --task NAME --lane LANE --model MODEL [--body-chars N]   -> {"cost_est":..,"tokens_est":..,"basis":".."}
  estimate.py record  --task NAME --model MODEL --predicted X --actual Y         -> appends state/system/estimates.jsonl
  estimate.py report                                                             -> accuracy table (median ratio per task/model)
Method: median of the last 10 actual costs for the same task; else same lane; else a per-model prior scaled by body size.
Model weights (per token): fable 3.3, sonnet 1.0, haiku 0.3 (from API list prices; plan usage tracks the same shape).
"""
import argparse, json, os, statistics, sys, datetime as dt
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[1]))
EVENTS = HOME / "briefs" / "data" / "events.jsonl"
EST = HOME / "state" / "system" / "estimates.jsonl"
WEIGHT = {"fable": 3.3, "sonnet": 1.0, "haiku": 0.3}
PRIOR_USD_PER_KCHAR = 0.06   # sonnet, per 1,000 chars of task body, rough starting point until history exists


def weight(model):
    m = (model or "").lower()
    return next((w for k, w in WEIGHT.items() if k in m), 1.0)


def events():
    if not EVENTS.exists(): return []
    out = []
    for l in EVENTS.read_text(encoding="utf-8").splitlines():
        try: out.append(json.loads(l))
        except ValueError: pass
    return out


def predict(task, lane, model, body_chars):
    ends = [e for e in events() if e.get("type") == "task_end" and float(e.get("cost_usd") or 0) > 0]
    same = [float(e["cost_usd"]) for e in ends if e.get("task") == task][-10:]
    if len(same) >= 2:
        return {"cost_est": round(statistics.median(same), 4), "basis": "task history (%d runs)" % len(same)}
    lane_runs = [float(e["cost_usd"]) * weight(model) / weight(e.get("model")) for e in ends if e.get("lane") == lane][-10:]
    if len(lane_runs) >= 3:
        return {"cost_est": round(statistics.median(lane_runs), 4), "basis": "lane history (%d runs, model-adjusted)" % len(lane_runs)}
    est = PRIOR_USD_PER_KCHAR * max(body_chars, 500) / 1000 * weight(model)
    return {"cost_est": round(est, 4), "basis": "prior"}


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("predict"); p.add_argument("--task", required=True); p.add_argument("--lane", default="general"); p.add_argument("--model", default=""); p.add_argument("--body-chars", type=int, default=1000)
    r = sub.add_parser("record"); r.add_argument("--task", required=True); r.add_argument("--model", default=""); r.add_argument("--predicted", type=float, required=True); r.add_argument("--actual", type=float, required=True)
    sub.add_parser("report")
    a = ap.parse_args()
    if a.cmd == "predict":
        out = predict(a.task, a.lane, a.model, a.body_chars)
        secs = []
        for e in events():
            if e.get("type") == "task_end" and e.get("task") == a.task:
                m = __import__("re").search(r"(\d+)s,", e.get("note", ""))
                if m: secs.append(int(m.group(1)))
        out["secs_est"] = int(statistics.median(secs[-10:])) if secs else 1200
        out["tokens_est"] = int(out["cost_est"] / (0.000015 * weight(a.model)))  # rough: output-token price of sonnet
        print(json.dumps(out))
    elif a.cmd == "record":
        EST.parent.mkdir(parents=True, exist_ok=True)
        ratio = round(a.actual / a.predicted, 3) if a.predicted else None
        with open(EST, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "task": a.task, "model": a.model, "predicted": a.predicted, "actual": a.actual, "ratio": ratio}) + "\n")
        print(json.dumps({"ok": True, "ratio": ratio}))
    elif a.cmd == "report":
        rows = [json.loads(l) for l in EST.read_text(encoding="utf-8").splitlines() if l.strip()] if EST.exists() else []
        by = {}
        for r in rows:
            if r.get("ratio"): by.setdefault((r["task"], r["model"]), []).append(r["ratio"])
        if not rows:
            print("no estimates recorded yet"); return
        print("%-28s %-22s %5s %8s" % ("task", "model", "runs", "actual/predicted (median)"))
        for (t, m), rs in sorted(by.items()):
            print("%-28s %-22s %5d %8.2f" % (t, m, len(rs), statistics.median(rs)))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
