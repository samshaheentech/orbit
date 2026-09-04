#!/usr/bin/env python3
"""
orbit/lanes/career/resume_loop.py, the blind resume loop (Fire 5).

One champion, config/lanes/career/resume/champion.md. For every lead Sam tagged
go, and once a week with no posting at all, three separate `claude -p`
processes run, each with its own prompt and no tools:

  improver  (fable)   sees the champion and the posting. Nothing else.
  grader A  (sonnet)  sees champion, challenger, posting, config/user.md, rulings.
  grader B  (fable)   same inputs, a different rubric. Never sees grader A.

The challenger surfaces in the webapp only if both graders score it at least
MIN_MARGIN above the champion and grader B lists zero rulings violations.
Otherwise it is discarded and its scores go to state/career/resume-log.jsonl.

Usage:
  python3 lanes/career/resume_loop.py [--dry-run] [--force-base]
                                     [--home DIR] [--fire ID] [--task-name NAME]

  --dry-run   swaps every claude call for a fixture under lanes/career/fixtures/resume/,
              writes everything under state/career/resume-dryrun/, and proves
              the improver prompt contains nothing from config/user.md.
              ORBIT_DRY_RUN=1 does the same, for a run through run.sh.

Runs from run.sh as an `exec:` task. Stdlib only, Python 3.9. Always exits 0;
the last lines are the STATUS block run.sh parses.
"""
import argparse
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

CHAMPION_ID = "resume-champion-v33"
CHAMPION_VERSION = "v33"
MAX_POSTINGS_PER_RUN = 3
MIN_MARGIN = 5
MAX_ERROR_ATTEMPTS = 2          # a posting that errored gets one more try, then it is done
CLAUDE_TIMEOUT_SEC = 900
FETCH_TIMEOUT_SEC = 20
POSTING_MAX_CHARS = 12000
POSTING_MIN_CHARS = 400         # less than this after HTML stripping means a JS-rendered page
BASE_TARGET = ("senior/staff embedded and platform roles at top-tier autonomy "
               "and AI companies")
MODELS = {"improver": "claude-fable-5-1",
          "grader_a": "claude-sonnet-5",
          "grader_b": "claude-fable-5-1"}
RESUME_START, RESUME_END = "<!-- resume:start -->", "<!-- resume:end -->"
DRY_SANDBOX = "resume-dryrun"


# ---------------------------------------------------------------- helpers

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clip(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 3].rstrip() + "..."


def read(p):
    return Path(p).read_text(encoding="utf-8")


def write(p, text):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class Paths:
    def __init__(self, home, sandbox=None):
        self.home = home
        self.res = home / "config" / "lanes" / "career" / "resume"
        self.champion = self.res / "champion.md"
        self.rulings = self.res / "rulings.md"
        self.prompts = self.res / "prompts"
        self.user_md = home / "config" / "user.md"
        self.emit = home / "system" / "emit.py"
        self.fixtures = Path(__file__).resolve().parent / "fixtures" / "resume"
        root = sandbox or home
        self.data_home = root                      # ORBIT_HOME handed to emit.py
        self.events = root / "briefs" / "data" / "events.jsonl"
        self.items = root / "briefs" / "data" / "items"
        self.state = root / "state" / "career"
        self.attempts = self.state / "resume-attempts.json"
        self.log = self.state / "resume-log.jsonl"
        self.approved = root / "config" / "lanes" / "career" / "resume" / "approved"


# ---------------------------------------------------------------- the log

def read_events(path):
    evs = []
    if not path.exists():
        return evs
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                evs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return evs


def fold(events):
    """Fold the append-only log into current items, the same way the webapp does."""
    items = {}
    for e in events:
        t, i = e.get("type"), e.get("id")
        if t == "item" and i:
            prev = items.get(i, {})
            meta = dict(prev.get("meta") or {})
            meta.update(e.get("meta") or {})
            it = dict(prev)
            it.update(e)
            it["meta"] = meta
            it["actions"] = list(prev.get("actions", []))
            it["hidden"] = prev.get("hidden", False)
            items[i] = it
        elif t == "item_update" and i in items:
            p = e.get("patch") or {}
            it = items[i]
            meta = dict(it.get("meta") or {})
            meta.update(p.get("meta") or {})
            it.update({k: v for k, v in p.items() if k != "meta"})
            it["meta"] = meta
        elif t == "item_action" and i in items:
            a = e.get("action")
            it = items[i]
            it["actions"].append(a)
            if a in ("skip", "prune"):
                it["hidden"] = True
    return items


def load_attempts(p):
    d = {}
    if p.exists():
        try:
            d = json.loads(read(p))
        except json.JSONDecodeError:
            d = {}
    d.setdefault("jobs", {})
    d.setdefault("approvals", {})
    d.setdefault("next_version", 1)
    return d


def save_attempts(p, d):
    write(p, json.dumps(d, indent=2, sort_keys=True))


def attempt_allowed(attempts, key):
    rec = attempts["jobs"].get(key)
    if not rec:
        return True
    if rec.get("outcome") in ("surfaced", "discarded"):
        return False
    return int(rec.get("errors", 1)) < MAX_ERROR_ATTEMPTS


def append_log(p, rec):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- work list

def leads_needing_challenger(items, attempts):
    have = {(it.get("meta") or {}).get("posting") for it in items.values() if it.get("kind") == "resume"}
    out = []
    for it in items.values():
        if it.get("kind") != "lead" or it.get("hidden"):
            continue
        if "go" not in it["actions"]:
            continue
        if it["id"] in have or not attempt_allowed(attempts, it["id"]):
            continue
        out.append(it)
    out.sort(key=lambda it: (-float((it.get("meta") or {}).get("score") or 0), it.get("ts", "")))
    return out


def base_key(today):
    y, w, _ = today.isocalendar()
    return "base-%d-W%02d" % (y, w)


def base_due(today, attempts, force):
    if force:
        return attempt_allowed(attempts, base_key(today))
    return today.weekday() == 6 and attempt_allowed(attempts, base_key(today))


# ---------------------------------------------------------------- posting text

class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
             "section", "article", "header", "footer", "table", "dd", "dt"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, d):
        if not self.skip:
            self.parts.append(d)


def html_to_text(raw):
    p = _Text()
    p.feed(raw)
    lines = [" ".join(ln.split()) for ln in "".join(p.parts).splitlines()]
    return "\n".join(ln for ln in lines if ln)


def fetch_posting(url):
    """Plain urllib, fail soft. Returns (text or None, note)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 orbit-career-lane/1.0"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as r:
            ctype = r.headers.get("Content-Type", "")
            raw = r.read(2_000_000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001, any network failure is a fallback, never a crash
        return None, "%s: %s" % (type(e).__name__, str(e)[:120])
    text = html_to_text(raw) if ("html" in ctype or "<html" in raw[:4000].lower()) else raw
    text = text[:POSTING_MAX_CHARS]
    if len(text) < POSTING_MIN_CHARS:
        return None, "fetched only %d chars of text, probably a JS-rendered page" % len(text)
    return text, "fetched %d chars" % len(text)


def fallback_posting(paths, lead):
    meta = lead.get("meta") or {}
    parts = ["Title: %s" % lead.get("title", ""),
             "Company: %s" % meta.get("company", ""),
             "Summary: %s" % lead.get("body", ""),
             "URL: %s" % (meta.get("url") or "n/a")]
    m = re.search(r"(\d{4}-\d{2}-\d{2})$", lead.get("id", ""))
    d = m.group(1) if m else str(lead.get("ts", ""))[:10]
    table = paths.items / ("leads-%s.md" % d)
    if table.exists():
        company = str(meta.get("company") or "").lower()
        rows = [ln for ln in read(table).splitlines()
                if lead["id"] in ln or (company and company in ln.lower())]
        if rows:
            parts.append("Scored table rows from %s:\n%s" % (table.name, "\n".join(rows[:10])))
    return "\n".join(parts)


def get_posting(lead, paths, dry):
    if dry:
        return read(paths.fixtures / "posting.txt"), "fixture"
    meta = lead.get("meta") or {}
    head = "Company: %s\nTitle: %s\nURL: %s\n\n" % (meta.get("company", ""), lead.get("title", ""), meta.get("url") or "n/a")
    url = str(meta.get("url") or "")
    if url.startswith("http"):
        text, note = fetch_posting(url)
        if text:
            return head + text, "fetched (%s)" % note
        return fallback_posting(paths, lead), "fallback (%s)" % note
    return fallback_posting(paths, lead), "fallback (no url on the lead)"


# ---------------------------------------------------------------- claude

def render(template, **vals):
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: vals.get(m.group(1), m.group(0)), template)


def parse_json_result(text):
    if not isinstance(text, str):
        return None, "result is not a string"
    s = text.strip()
    s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s).strip()
    try:
        return json.loads(s), None
    except json.JSONDecodeError:
        pass
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b > a:
        try:
            return json.loads(s[a:b + 1]), None
        except json.JSONDecodeError as e:
            return None, "JSON parse failed: %s" % e
    return None, "no JSON object in result"


class Call:
    """One `claude -p` process. Construct to start, finish() to collect.
    Two Calls constructed back to back run concurrently and never share state."""

    def __init__(self, prompt, model, fixture=None):
        self.obj, self.err, self.cost, self.proc = None, None, 0.0, None
        if fixture is not None:
            self.obj = fixture
            return
        cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "json",
               "--permission-mode", "dontAsk", "--tools", "", "--max-turns", "1",
               "--no-session-persistence"]
        env = dict(os.environ)
        env.pop("CLAUDECODE", None)   # allow a by-hand run from inside a Claude Code shell
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         encoding="utf-8", errors="replace", env=env)
        except FileNotFoundError:
            self.err = "claude not on PATH"

    def finish(self, timeout=CLAUDE_TIMEOUT_SEC):
        if self.proc is None:
            return self
        try:
            out, err = self.proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.communicate()
            self.err = "timeout after %ds" % timeout
            return self
        if not out.strip():
            self.err = "empty output, exit %d: %s" % (self.proc.returncode, err.strip()[:300])
            return self
        try:
            d = json.loads(out)
        except json.JSONDecodeError:
            self.err = "claude output was not JSON: %s" % out[:200]
            return self
        try:
            self.cost = float(d.get("total_cost_usd") or 0)
        except (TypeError, ValueError):
            self.cost = 0.0
        if d.get("is_error"):
            self.err = "claude error: %s" % str(d.get("result", ""))[:300]
            return self
        self.obj, self.err = parse_json_result(d.get("result", ""))
        return self


def validate_improver(obj):
    if not isinstance(obj, dict):
        return "improver output is not an object"
    r = obj.get("resume_md")
    if not isinstance(r, str) or len(r.strip()) < 500:
        return "resume_md missing or too short"
    e = obj.get("edits")
    if not isinstance(e, list) or any(not isinstance(x, dict) for x in e):
        return "edits missing or malformed"
    return None


def validate_grade(obj, who):
    if not isinstance(obj, dict):
        return "%s output is not an object" % who
    for side in ("champion", "challenger"):
        d = obj.get(side)
        if not isinstance(d, dict):
            return "%s: missing %s" % (who, side)
        dims = d.get("dims") if isinstance(d.get("dims"), dict) else {}
        tot = d.get("total")
        if tot is None and dims:
            tot = sum(v for v in dims.values() if isinstance(v, (int, float)))
        try:
            tot = float(tot)
        except (TypeError, ValueError):
            return "%s: %s.total is not a number" % (who, side)
        if not 0 <= tot <= 100:
            return "%s: %s.total %s out of range" % (who, side, tot)
        d["total"], d["dims"] = tot, dims
    v = obj.get("violations")
    if v is None:
        obj["violations"] = []
    elif not isinstance(v, list):
        return "%s: violations is not a list" % who
    return None


# ---------------------------------------------------------------- decision

def decide(a, b):
    """Both graders at least MIN_MARGIN above the champion, and grader B finds no violation."""
    da = a["challenger"]["total"] - a["champion"]["total"]
    db = b["challenger"]["total"] - b["champion"]["total"]
    reasons = []
    if da < MIN_MARGIN:
        reasons.append("grader A margin %+.0f, needs +%d" % (da, MIN_MARGIN))
    if db < MIN_MARGIN:
        reasons.append("grader B margin %+.0f, needs +%d" % (db, MIN_MARGIN))
    if b["violations"]:
        reasons.append("%d rulings violation(s): %s" % (len(b["violations"]),
                       clip("; ".join(str(x) for x in b["violations"]), 300)))
    return not reasons, reasons, da, db


def decision_selftest():
    def g(c, ch, v=None):
        return {"champion": {"total": c}, "challenger": {"total": ch}, "violations": v or []}
    cases = [("both +8, no violations", g(70, 78), g(70, 78), True),
             ("both +5 exactly", g(70, 75), g(70, 75), True),
             ("A +4, B +10", g(70, 74), g(70, 80), False),
             ("A +10, B +3", g(70, 80), g(70, 73), False),
             ("both +10, one violation", g(70, 80), g(70, 80, ["em-dash in summary"]), False),
             ("challenger worse", g(70, 60), g(70, 60), False)]
    return [(name, decide(a, b)[0] == want) for name, a, b, want in cases]


# ---------------------------------------------------------------- outputs

def write_item_file(path, job, version, challenger, edits, a, b, fire, today, posting_note):
    lines = ["# Challenger %s" % version, ""]
    if job["kind"] == "lead":
        lead = job["lead"]
        lines += ["Posting: %s, %s" % (lead["id"], lead.get("title", "")),
                  "URL: %s" % ((lead.get("meta") or {}).get("url") or "n/a"),
                  "Posting text: %s" % posting_note]
    else:
        lines += ["Posting: none, weekly base run. Target: %s" % BASE_TARGET]
    viol = b.get("violations") or []
    lines += ["Date: %s, fire %s" % (today, fire), "",
              "Grader A: champion %.0f, challenger %.0f (%+.0f). Grader B: champion %.0f, challenger %.0f (%+.0f). Rulings violations: %d"
              % (a["champion"]["total"], a["challenger"]["total"], a["challenger"]["total"] - a["champion"]["total"],
                 b["champion"]["total"], b["challenger"]["total"], b["challenger"]["total"] - b["champion"]["total"], len(viol)),
              "", RESUME_START, challenger.strip(), RESUME_END, "", "## Edits", ""]
    for n, e in enumerate(edits, 1):
        lines += ["%d. **%s**" % (n, e.get("where", "")),
                  "   from: %s" % e.get("from", ""),
                  "   to: %s" % e.get("to", ""),
                  "   why: %s" % e.get("why", ""), ""]
    if not edits:
        lines += ["(no edits listed)", ""]
    for name, g in (("Grader A", a), ("Grader B", b)):
        lines += ["## %s" % name, "", "```json", json.dumps(g, indent=2, ensure_ascii=False), "```", ""]
    write(path, "\n".join(lines))


def extract_resume(text):
    s, e = text.find(RESUME_START), text.find(RESUME_END)
    if s != -1 and e > s:
        return text[s + len(RESUME_START):e].strip() + "\n"
    return text


def emit_item(paths, fire, iid, title, body, meta):
    env = dict(os.environ, ORBIT_HOME=str(paths.data_home), ORBIT_FIRE=fire, ORBIT_LANE="career")
    r = subprocess.run([sys.executable, str(paths.emit), "item", "--kind", "resume", "--id", iid,
                        "--title", clip(title, 90), "--body", clip(body, 300),
                        "--meta", json.dumps(meta), "--lane", "career"],
                       capture_output=True, encoding="utf-8", errors="replace", env=env)
    return None if r.returncode == 0 else (r.stderr or r.stdout).strip()[:300]


def mission_file(paths):
    p = os.environ.get("ORBIT_MISSION_FILE", "")
    if not p and paths.user_md.exists():
        m = re.search(r"^\s*-?\s*Mission file:\s*(.+?)\s*$", read(paths.user_md), re.M | re.I)
        if m:
            p = m.group(1)
    return Path(os.path.expanduser(p)) if p else None


def append_mission_line(mpath, line):
    text = read(mpath) if mpath.exists() else ""
    heading = "## Tailored variants"
    if heading not in text:
        text = text.rstrip("\n") + ("\n\n" if text else "") + heading + "\n"
    write(mpath, text.rstrip("\n") + "\n" + line + "\n")


# ---------------------------------------------------------------- one job

class Ctx:
    def __init__(self, paths, fire, today, dry, champion, rulings, profile, prompts, attempts):
        self.paths, self.fire, self.today, self.dry = paths, fire, today, dry
        self.champion, self.rulings, self.profile, self.prompts = champion, rulings, profile, prompts
        self.attempts = attempts
        self.improver_prompts = []

    def fixture(self, role, job):
        if not self.dry:
            return None
        name = {"improver": "improver.json", "grader_a": "grader_a.json",
                "grader_b": "grader_b_pass.json" if job["dry_index"] % 2 == 0 else "grader_b_violation.json"}[role]
        return json.loads(read(self.paths.fixtures / name))


def run_job(job, ctx):
    paths, today = ctx.paths, ctx.today
    rec = {"ts": now_iso(), "fire": ctx.fire, "job": job["key"], "kind": job["kind"],
           "outcome": "error", "cost_usd": 0.0}
    if job["kind"] == "base":
        posting = "No specific posting. Tailor for: %s." % BASE_TARGET
        rec["posting_source"] = "base"
    else:
        posting, rec["posting_source"] = get_posting(job["lead"], paths, ctx.dry)

    # 1. improver, blind: its prompt is built from three strings and nothing else
    imp_prompt = render(ctx.prompts["improver"], POSTING=posting, CHAMPION=ctx.champion)
    ctx.improver_prompts.append((job["key"], imp_prompt, posting))
    imp = Call(imp_prompt, MODELS["improver"], fixture=ctx.fixture("improver", job)).finish()
    rec["cost_usd"] += imp.cost
    problem = imp.err or validate_improver(imp.obj)
    if problem:
        rec["error"] = "improver: " + problem
        return rec
    challenger, edits = imp.obj["resume_md"], imp.obj["edits"]
    rec["edits"] = edits

    # 2. two graders, informed, independent: separate processes, started together
    common = dict(POSTING=posting, CHAMPION=ctx.champion, CHALLENGER=challenger,
                  EDITS=json.dumps(edits, indent=1, ensure_ascii=False),
                  PROFILE=ctx.profile, RULINGS=ctx.rulings)
    ga = Call(render(ctx.prompts["grader_a"], **common), MODELS["grader_a"], fixture=ctx.fixture("grader_a", job))
    gb = Call(render(ctx.prompts["grader_b"], **common), MODELS["grader_b"], fixture=ctx.fixture("grader_b", job))
    ga.finish()
    gb.finish()
    rec["cost_usd"] += ga.cost + gb.cost
    problem = ga.err or validate_grade(ga.obj, "grader A") or gb.err or validate_grade(gb.obj, "grader B")
    if problem:
        rec["error"] = problem
        return rec
    a, b = ga.obj, gb.obj
    rec["a"], rec["b"] = a, b
    rec["violations"] = b["violations"]

    # 3. decide
    ok, reasons, da, db = decide(a, b)
    rec["margins"] = {"a": da, "b": db}
    if not ok:
        rec["outcome"], rec["reason"] = "discarded", reasons
        return rec

    version = "v33+%d" % ctx.attempts["next_version"]
    ctx.attempts["next_version"] += 1
    item_id = job["file_id"]
    path = paths.items / (item_id + ".md")
    write_item_file(path, job, version, challenger, edits, a, b, ctx.fire, today, rec["posting_source"])
    if job["kind"] == "lead":
        title = "%s challenger: %s" % (version, job["lead"].get("title", job["key"]))
        posting_ref = job["lead"]["id"]
    else:
        title = "%s base challenger, generic senior/staff target" % version
        posting_ref = "base"
    first_why = (edits[0].get("why") if edits else "") or ""
    body = "A %.0f vs %.0f, B %.0f vs %.0f. %d edit%s. %s" % (
        a["challenger"]["total"], a["champion"]["total"], b["challenger"]["total"], b["champion"]["total"],
        len(edits), "" if len(edits) == 1 else "s", first_why)
    meta = {"status": "challenger", "version": version,
            "graders": {"a": round(a["challenger"]["total"]), "b": round(b["challenger"]["total"])},
            "posting": posting_ref, "path": str(path)}
    err = emit_item(paths, ctx.fire, item_id, title, body, meta)
    rec.update({"version": version, "item_id": item_id, "path": str(path)})
    if err:
        rec["error"] = "emit failed: " + err
        return rec
    rec["outcome"] = "surfaced"
    return rec


# ---------------------------------------------------------------- approvals

def process_approvals(items, attempts, paths, today, notes):
    done = attempts["approvals"]
    out = []
    mpath = mission_file(paths)
    for it in items.values():
        meta = it.get("meta") or {}
        if it.get("kind") != "resume" or meta.get("status") != "challenger":
            continue
        if "approve" not in it["actions"] or it["id"] in done:
            continue
        src = Path(str(meta.get("path") or ""))
        if not src.is_absolute():
            src = paths.data_home / src
        if not src.exists():
            done[it["id"]] = {"date": today.isoformat(), "error": "file missing: %s" % src}
            notes.append("approve %s: challenger file missing at %s" % (it["id"], src))
            continue
        posting = str(meta.get("posting") or "base")
        dest = paths.approved / ("%s.md" % (posting if posting != "base" else "base-%s" % today.isoformat()))
        write(dest, extract_resume(read(src)))
        done[it["id"]] = {"date": today.isoformat(), "path": str(dest)}
        out.append(dest)
        if posting == "base":
            notes.append("approved base challenger %s, promote by replacing champion.md (copy at %s)" % (it["id"], dest))
            continue
        line = "- %s: %s approved as %s for %s, file %s" % (today.isoformat(), it["id"], meta.get("version", "?"), posting, dest)
        if mpath and mpath.exists():
            append_mission_line(mpath, line)
            notes.append("mission file updated for %s" % posting)
        else:
            notes.append("mission file not configured (add 'Mission file: <path>' to config/user.md or set ORBIT_MISSION_FILE); approved copy at %s" % dest)
    return out


# ---------------------------------------------------------------- dry run

def setup_dry(paths, today):
    sb = paths.home / "state" / "career" / DRY_SANDBOX
    if sb.exists():
        shutil.rmtree(sb)
    p = Paths(paths.home, sandbox=sb)
    p.items.mkdir(parents=True, exist_ok=True)
    p.state.mkdir(parents=True, exist_ok=True)
    d = today.isoformat()
    fx = json.loads(read(p.fixtures / "improver.json"))
    ga = json.loads(read(p.fixtures / "grader_a.json"))
    gb = json.loads(read(p.fixtures / "grader_b_pass.json"))
    # a challenger Sam already approved, so the approval path runs too
    prior_lead = "lead-figure-platform-2026-08-28"
    prior_id = "resume-%s-2026-08-30" % prior_lead
    prior_path = p.items / (prior_id + ".md")
    prior_job = {"kind": "lead", "lead": {"id": prior_lead, "title": "Figure, Staff Embedded Software Engineer, Humanoid Platform",
                                          "meta": {"url": "https://example.invalid/figure"}}}
    write_item_file(prior_path, prior_job, "v33+0", fx["resume_md"], fx["edits"], ga, gb, "fire-fixture", "2026-08-30", "fixture")
    ts = "%sT06:00:00Z" % d
    evs = [
        {"ts": ts, "fire": "fire-fixture", "type": "item", "lane": "career", "kind": "lead", "id": "lead-nvidia-drive-%s" % d,
         "title": "NVIDIA, Senior Software Engineer, DRIVE platform integration",
         "body": "Remote US, DRIVE Thor stack, $215k to $290k base. Score 92.",
         "meta": {"score": 92, "company": "NVIDIA", "url": "https://example.invalid/nvidia", "comp": "215-290k", "remote": "remote"}},
        {"ts": ts, "type": "item_action", "id": "lead-nvidia-drive-%s" % d, "action": "go", "source": "webapp"},
        {"ts": ts, "fire": "fire-fixture", "type": "item", "lane": "career", "kind": "lead", "id": "lead-zoox-platform-%s" % d,
         "title": "Zoox, Staff Software Engineer, Vehicle Compute Platform",
         "body": "Hybrid Foster City, staff level, compute platform bring-up. Score 85.",
         "meta": {"score": 85, "company": "Zoox", "url": "https://example.invalid/zoox", "comp": None, "remote": "hybrid"}},
        {"ts": ts, "type": "item_action", "id": "lead-zoox-platform-%s" % d, "action": "go", "source": "webapp"},
        {"ts": ts, "fire": "fire-fixture", "type": "item", "lane": "career", "kind": "lead", "id": "lead-anduril-infra-%s" % d,
         "title": "Anduril, Staff Systems Engineer, Perception Infrastructure", "body": "Not tagged go; the loop must ignore it.",
         "meta": {"score": 70, "company": "Anduril", "url": "https://example.invalid/anduril"}},
        {"ts": "2026-08-30T06:00:00Z", "fire": "fire-fixture", "type": "item", "lane": "career", "kind": "resume", "id": prior_id,
         "title": "v33+0 challenger: Figure, Staff Embedded Software Engineer", "body": "fixture",
         "meta": {"status": "challenger", "version": "v33+0", "graders": {"a": 83, "b": 83}, "posting": prior_lead, "path": str(prior_path)}},
        {"ts": "2026-08-31T06:00:00Z", "type": "item_action", "id": prior_id, "action": "approve", "source": "webapp"},
    ]
    with open(p.events, "w", encoding="utf-8") as f:
        for e in evs:
            f.write(json.dumps(e) + "\n")
    return p


def blindness_check(ctx):
    """Two independent proofs on every improver prompt built this run:
    1. no line of config/user.md (or rulings.md) appears in it;
    2. every line of it comes from improver.md, champion.md, or the posting text."""
    forbidden = []
    for src in (ctx.profile, ctx.rulings):
        forbidden += [ln.strip("-#* ").strip() for ln in src.splitlines()]
    forbidden = [ln for ln in forbidden if len(ln) >= 12]
    template_lines = set(ln.strip() for ln in ctx.prompts["improver"].splitlines())
    champion_lines = set(ln.strip() for ln in ctx.champion.splitlines())
    results = []
    for key, prompt, posting in ctx.improver_prompts:
        leaks = [ln for ln in forbidden if ln in prompt]
        allowed = template_lines | champion_lines | set(ln.strip() for ln in posting.splitlines())
        foreign = [ln for ln in (x.strip() for x in prompt.splitlines()) if ln and ln not in allowed]
        for tok in ("config/user.md", "user.md", "rulings.md", "mission file"):
            if tok in prompt:
                leaks.append("token '%s'" % tok)
        results.append((key, leaks, foreign))
    return results


# ---------------------------------------------------------------- main

def print_status(kind, changed, verified, notes, nxt, cost):
    print("COST_USD: %.4f" % cost)
    print("STATUS: %s" % kind)
    print("Changed: %s" % (changed or "nothing"))
    print("Verified: %s" % (verified or "nothing to verify"))
    print("Notes: %s" % (notes or "none"))
    print("Next: %s" % nxt)


def requeue(paths, task_name):
    src = paths.home / "running" / (task_name + ".md")
    if not src.exists():
        return False
    text = read(src)
    cut = text.find("\n---\n## Agent report")
    if cut != -1:
        text = text[:cut].rstrip() + "\n"
    write(paths.home / "queue" / (task_name + ".md"), text)
    return True


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Orbit blind resume loop")
    ap.add_argument("--dry-run", action="store_true", help="fixtures instead of claude, writes under state/career/%s/" % DRY_SANDBOX)
    ap.add_argument("--force-base", action="store_true", help="run the weekly base job today")
    ap.add_argument("--home", default=os.environ.get("ORBIT_HOME") or str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--fire", default=os.environ.get("ORBIT_FIRE", "manual"))
    ap.add_argument("--task-name", default="130-career-resume")
    args = ap.parse_args()
    dry = args.dry_run or os.environ.get("ORBIT_DRY_RUN") == "1"
    home = Path(args.home).expanduser().resolve()
    paths = Paths(home)
    today = date.today()
    fire = args.fire

    needed = [paths.champion, paths.rulings] + [paths.prompts / (k + ".md") for k in ("improver", "grader_a", "grader_b")]
    missing = [p for p in needed if not p.exists()]
    if missing:
        print("resume loop: cannot run, missing %s" % ", ".join(str(m) for m in missing))
        hint = " See %s." % (paths.res / "README.md") if missing[0] == paths.champion else ""
        print_status("BLOCKED", "nothing", "not run, precondition missing",
                     "missing %s.%s" % (missing[0], hint),
                     "add the file, then move blocked/%s.md back into queue/" % args.task_name, 0.0)
        return 0

    champion, rulings = read(paths.champion), read(paths.rulings)
    prompts = {k: read(paths.prompts / (k + ".md")) for k in ("improver", "grader_a", "grader_b")}
    profile = read(paths.user_md) if paths.user_md.exists() else ""

    if dry:
        paths = setup_dry(paths, today)
        print("DRY RUN: fixtures instead of claude, every write goes under %s" % paths.data_home)
    attempts = load_attempts(paths.attempts)
    items = fold(read_events(paths.events))
    changed, notes, cost = [], [], 0.0

    # exactly one champion item in the log
    if CHAMPION_ID not in items:
        err = emit_item(paths, fire, CHAMPION_ID, "v33, the champion",
                        "Every challenger is graded against this document by two independent graders. It changes only when Sam replaces champion.md.",
                        {"status": "champion", "version": CHAMPION_VERSION, "graders": {}, "posting": "",
                         "path": "config/lanes/career/resume/champion.md"})
        if err:
            notes.append("champion emit failed: " + err)
        else:
            changed.append("emitted " + CHAMPION_ID)

    # work list: go-tagged leads without a challenger, capped, plus the weekly base run
    leads = leads_needing_challenger(items, attempts)
    if len(leads) > MAX_POSTINGS_PER_RUN:
        notes.append("%d go-tagged leads waiting, cap is %d per run, the rest wait for the next fire" % (len(leads), MAX_POSTINGS_PER_RUN))
    jobs = [{"key": it["id"], "kind": "lead", "lead": it, "file_id": "resume-%s-%s" % (it["id"], today.isoformat())}
            for it in leads[:MAX_POSTINGS_PER_RUN]]
    if base_due(today, attempts, args.force_base):
        jobs.append({"key": base_key(today), "kind": "base", "lead": None, "file_id": "resume-base-%s" % today.isoformat()})
    for i, j in enumerate(jobs):
        j["dry_index"] = i

    ctx = Ctx(paths, fire, today, dry, champion, rulings, profile, prompts, attempts)
    counts = {"surfaced": 0, "discarded": 0, "error": 0}
    print("resume loop: %d job(s): %s" % (len(jobs), ", ".join(j["key"] for j in jobs) or "none"))
    for job in jobs:
        rec = run_job(job, ctx)
        cost += rec["cost_usd"]
        counts[rec["outcome"]] += 1
        prev = attempts["jobs"].get(job["key"], {})
        if rec["outcome"] == "error":
            attempts["jobs"][job["key"]] = {"date": today.isoformat(), "fire": fire, "outcome": "error",
                                            "errors": int(prev.get("errors", 0)) + 1, "error": rec.get("error")}
            print("  %s: ERROR, %s" % (job["key"], rec.get("error")))
        else:
            attempts["jobs"][job["key"]] = {"date": today.isoformat(), "fire": fire, "outcome": rec["outcome"],
                                            "version": rec.get("version"), "item": rec.get("item_id")}
            a, b = rec["a"], rec["b"]
            scores = "A %.0f to %.0f, B %.0f to %.0f, %d violation(s)" % (
                a["champion"]["total"], a["challenger"]["total"], b["champion"]["total"], b["challenger"]["total"], len(b["violations"]))
            if rec["outcome"] == "surfaced":
                print("  %s: surfaced as %s (%s), posting %s" % (job["key"], rec["version"], scores, rec["posting_source"]))
                changed.append(rec["item_id"])
            else:
                print("  %s: discarded (%s): %s" % (job["key"], scores, "; ".join(rec["reason"])))
        append_log(paths.log, rec)
        save_attempts(paths.attempts, attempts)   # after every job, so a crash mid-run never re-runs a posting

    approved = process_approvals(items, attempts, paths, today, notes)
    changed += [str(p) for p in approved]
    save_attempts(paths.attempts, attempts)

    verified = "%d job(s): %d surfaced, %d discarded, %d error(s); %d approval(s) processed" % (
        len(jobs), counts["surfaced"], counts["discarded"], counts["error"], len(approved))
    blocked = None
    if dry:
        checks = blindness_check(ctx)
        for key, leaks, foreign in checks:
            ok = not leaks and not foreign
            print("  blindness %s: %s" % (key, "PASS, improver prompt built only from improver.md + champion.md + posting"
                                           if ok else "FAIL leaks=%s foreign=%s" % (leaks[:3], foreign[:3])))
            if not ok:
                blocked = "blindness check failed for %s" % key
        selftest = decision_selftest()
        for name, ok in selftest:
            print("  decision rule '%s': %s" % (name, "PASS" if ok else "FAIL"))
            if not ok:
                blocked = "decision self-test failed: %s" % name
        verified += "; blindness %s; decision self-test %s" % (
            "PASS" if all(not l and not f for _, l, f in checks) else "FAIL",
            "PASS" if all(ok for _, ok in selftest) else "FAIL")

    if blocked:
        print_status("BLOCKED", ", ".join(changed), verified, blocked, "fix the loop before it runs for real", cost)
        return 0
    if jobs and counts["error"] == len(jobs):
        print_status("PARTIAL", ", ".join(changed), verified, "; ".join(notes) or "every job errored, see state/career/resume-log.jsonl",
                     "run.sh retries on the next fire; a posting gets %d tries" % MAX_ERROR_ATTEMPTS, cost)
        return 0
    if requeue(paths, args.task_name):
        changed.append("queue/%s.md re-queued" % args.task_name)
    print_status("DONE", ", ".join(changed), verified, "; ".join(notes), "nothing", cost)
    return 0


if __name__ == "__main__":
    sys.exit(main())
