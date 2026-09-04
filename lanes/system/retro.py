#!/usr/bin/env python3
"""
Sunday 22:00: review the week, propose changes to Orbit itself, apply what Sam approved last week.
  python3 lanes/system/retro.py [--now ISO] [--dry-run] [--force] [--apply-only]
Proposals are `proposal` items: {target, find, replace, why}. Approved ones are applied by exact
substring replacement on a branch orbit/retro-<date>, never on main. Nothing is ever retried silently.
"""
import argparse, datetime as dt, json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

SLOT = 22
TASK = "900-system-retro"
ALLOWED_TARGETS = ("queue/", "config/lanes/", "system/prompt.md", "lanes/")


def week(now):
    since = now - dt.timedelta(days=7)
    ev = [e for e in C.read_events() if C.ts(e) >= since]
    ends = [e for e in ev if e.get("type") == "task_end"]
    by_task = {}
    for e in ends:
        t = by_task.setdefault(e["task"], {"runs": 0, "done": 0, "blocked": 0, "cost": 0.0, "model": e.get("model", "")})
        t["runs"] += 1; t["cost"] = round(t["cost"] + float(e.get("cost_usd") or 0), 2)
        if e["status"] == "DONE": t["done"] += 1
        if e["status"] in ("BLOCKED", "ERROR", "TIMEOUT"): t["blocked"] += 1
    produced = len({e["id"] for e in ev if e.get("type") == "item"})
    consumed = len({e["id"] for e in ev if e.get("type") == "item_action"})
    actions = {}
    for e in ev:
        if e.get("type") == "item_action": actions[e["action"]] = actions.get(e["action"], 0) + 1
    est = C.HOME / "state" / "system" / "estimates.jsonl"
    ratios = [json.loads(l)["ratio"] for l in est.read_text().splitlines() if l.strip() and json.loads(l).get("ratio")] if est.exists() else []
    assign = C.HOME / "state" / "system" / "assignments.md"
    return {"tasks": by_task, "produced": produced, "consumed": consumed, "actions": actions,
            "limits": sum(1 for e in ev if e.get("type") == "fire_limit"),
            "estimate_ratio_median": round(sorted(ratios)[len(ratios) // 2], 2) if ratios else None,
            "assignments": assign.read_text(encoding="utf-8")[-3000:] if assign.exists() else "",
            "system_prompt": (C.HOME / "system" / "prompt.md").read_text(encoding="utf-8")[:3000],
            "task_files": {p.name: p.read_text(encoding="utf-8")[:1500] for p in sorted((C.HOME / "queue").glob("*.md")) if not p.name.startswith("_")}}


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=str(cwd or C.HOME), capture_output=True, text=True)


def apply_approved(now):
    ev = C.read_events()
    props, acts = {}, {}
    for e in ev:
        if e.get("type") == "item" and e.get("kind") == "proposal": props[e["id"]] = dict(e)
        elif e.get("type") == "item_update" and e.get("id") in props: props[e["id"]].setdefault("meta", {}).update((e.get("patch") or {}).get("meta", {}))
        elif e.get("type") == "item_action" and e.get("id") in props: acts.setdefault(e["id"], []).append(e)
    todo = [p for pid, p in props.items() if not p.get("meta", {}).get("applied") and not p.get("meta", {}).get("failed")
            and any(a["action"] == "approve" for a in acts.get(pid, [])) and not any(a["action"] == "skip" and C.ts(a) > max(C.ts(x) for x in acts[pid] if x["action"] == "approve") for a in acts.get(pid, []))]
    if not todo: return []
    branch = "orbit/retro-%s" % now.date().isoformat()
    start = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
    if git("rev-parse", "--verify", branch).returncode != 0: git("branch", branch)
    git("checkout", "-q", branch)
    results = []
    try:
        for p in todo:
            m = p.get("meta", {}); target = C.HOME / m.get("target", "")
            ok, why = False, ""
            if not any(m.get("target", "").startswith(a) for a in ALLOWED_TARGETS): why = "target outside allowed paths"
            elif not target.exists(): why = "target missing"
            else:
                text = target.read_text(encoding="utf-8")
                if text.count(m.get("find", "")) != 1 or not m.get("find"): why = "find text not unique in target"
                else:
                    target.write_text(text.replace(m["find"], m.get("replace", ""), 1), encoding="utf-8")
                    git("add", m["target"])
                    r = git("-c", "user.name=Orbit retro", "-c", "user.email=orbit@localhost", "commit", "-q", "-m", "retro: %s" % p.get("title", p["id"])[:60])
                    ok = r.returncode == 0; why = "" if ok else r.stderr.strip()[-200:]
                    if not ok: git("reset", "-q", "HEAD", m["target"]); git("checkout", "-q", "--", m["target"])
            C.emit("update", "--id", p["id"], "--patch", json.dumps({"meta": {"applied": now.date().isoformat(), "branch": branch} if ok else {"failed": now.date().isoformat(), "why": why}}))
            results.append((p["id"], ok, why))
    finally:
        git("checkout", "-q", start)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--now"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true"); ap.add_argument("--apply-only", action="store_true")
    a = ap.parse_args()
    now = C.parse_now(a.now)
    if not a.force and not C.in_band(now, C.sched()["plan_at"], 40):
        C.requeue(TASK); C.status("DONE", "nothing", "hour gate", "not my hour", "run Sunday 22:00"); return
    applied = apply_approved(now)
    if a.apply_only:
        C.requeue(TASK); C.status("DONE", "applied %d approved proposals" % sum(1 for r in applied if r[1]), str(applied), "", "nothing"); return
    w = week(now)
    prompt = (
        "You are Orbit's weekly retro. Review the week's data and propose at most 5 concrete changes to Orbit itself. "
        "A proposal edits exactly one file among queue/*.md, config/lanes/**, system/prompt.md, or lanes/** by replacing one exact "
        "substring with another. Each proposal needs: title (under 80 chars), target (repo-relative path), find (exact text that occurs "
        "once in the target), replace (new text), why (evidence from the data, one or two sentences). Also give worked (list) and didnt (list). "
        "Only propose what the evidence supports; no cosmetic edits; never propose changes to run.sh, server.py, or the webapp. "
        "Return strict JSON: {\"worked\":[],\"didnt\":[],\"proposals\":[{title,target,find,replace,why}]}.\n\nDATA:\n" + json.dumps(w, ensure_ascii=False))
    fixture = str(Path(__file__).parent / "fixtures" / "retro.json") if a.dry_run else None
    out, cost = C.call_claude(prompt, "claude-fable-5-1", fixture=fixture, timeout=600)
    n = 0
    if isinstance(out, dict):
        for i, p in enumerate((out.get("proposals") or [])[:5]):
            if not all(k in p for k in ("title", "target", "find", "replace")): continue
            pid = "proposal-%s-%d" % (now.date().isoformat(), i + 1)
            body = (p.get("why") or "")[:300]
            path = C.HOME / "briefs" / "data" / "items" / (pid + ".md"); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# %s\n\nTarget: `%s`\n\n## Why\n%s\n\n## Find\n```\n%s\n```\n\n## Replace\n```\n%s\n```\n" % (p["title"], p["target"], p.get("why", ""), p["find"], p["replace"]), encoding="utf-8")
            if C.emit("item", "--kind", "proposal", "--lane", "system", "--id", pid, "--title", p["title"][:90], "--body", body,
                      "--meta", json.dumps({"target": p["target"], "find": p["find"], "replace": p["replace"], "path": str(path.relative_to(C.HOME))})):
                n += 1
        summary = {"worked": out.get("worked", []), "didnt": out.get("didnt", [])}
        (C.HOME / "state" / "system").mkdir(parents=True, exist_ok=True)
        (C.HOME / "state" / "system" / ("retro-%s.json" % now.date().isoformat())).write_text(json.dumps({**summary, "week": w, "proposals": n}, indent=1), encoding="utf-8")
    C.requeue(TASK)
    C.status("DONE" if isinstance(out, dict) else "PARTIAL",
             "applied %d approved proposals; emitted %d new proposals" % (sum(1 for r in applied if r[1]), n),
             "week: %d tasks, %d produced, %d consumed, %d limits" % (len(w["tasks"]), w["produced"], w["consumed"], w["limits"]),
             ("retro model output" if isinstance(out, dict) else "model call failed; no proposals") + (("; failures: " + str([r for r in applied if not r[1]])) if any(not r[1] for r in applied) else ""),
             "approve or skip proposals in the webapp; approved ones apply next Sunday on branch orbit/retro-<date>", cost)


if __name__ == "__main__":
    main()
