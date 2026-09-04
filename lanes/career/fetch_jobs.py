#!/usr/bin/env python3
"""
orbit/lanes/career/fetch_jobs.py — pull current postings for every company in
config/lanes/career/companies.json, filter, dedupe, write new candidates.

Usage:
  python3 fetch_jobs.py [--fixtures] [--home <ORBIT_HOME>] [--fire <fire-id>]

Stdlib only. Never crashes on one company's failure — each company's fetch is
wrapped and errors are collected into the summary instead of raised.

Writes state/career/candidates-<fire>.json (new, unseen postings, newest
first, capped at 30) and updates state/career/seen.json. Prints a JSON
summary to stdout and exits 0.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

TITLE_KEYWORDS = [
    "embedded", "firmware", "platform", "systems", "integration", "autonomy",
    "adas", "robotics", "perception", "infrastructure", "software engineer",
]
EXCLUDE_KEYWORDS = [
    "intern", "internship", "new grad", "new-grad", "college grad",
    "sales", "recruiter", "recruiting", "account executive", "marketing",
    "student worker", "co-op", "apprentice",
]

CANDIDATE_CAP = 30
TIMEOUT = 20


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "orbit-career-lane/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    h = {"User-Agent": "orbit-career-lane/1.0", "Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(company, title, location, remote_hint, url, posted, snippet):
    return {
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "remote_hint": remote_hint,
        "url": url,
        "posted": posted,
        "snippet": (snippet or "").strip()[:500],
    }


# ---- per-ATS fetchers ----

def fetch_greenhouse(company, fixtures_dir=None):
    token = company["token"]
    if fixtures_dir:
        raw = json.loads((fixtures_dir / "greenhouse.json").read_text())
    else:
        raw = http_get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    out = []
    for j in raw.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        out.append(normalize(
            company["name"], j.get("title"), loc,
            "remote" if "remote" in loc.lower() else None,
            j.get("absolute_url"), j.get("updated_at"), j.get("content", ""),
        ))
    return out


def fetch_lever(company, fixtures_dir=None):
    token = company["token"]
    if fixtures_dir:
        raw = json.loads((fixtures_dir / "lever.json").read_text())
    else:
        raw = http_get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    out = []
    for j in raw:
        cats = j.get("categories", {}) or {}
        loc = cats.get("location", "")
        out.append(normalize(
            company["name"], j.get("text"), loc,
            "remote" if "remote" in (loc or "").lower() else None,
            j.get("hostedUrl"), j.get("createdAt"), j.get("descriptionPlain", ""),
        ))
    return out


def fetch_ashby(company, fixtures_dir=None):
    name_param = company.get("name_param", company["slug"])
    if fixtures_dir:
        raw = json.loads((fixtures_dir / "ashby.json").read_text())
    else:
        raw = http_get(f"https://api.ashbyhq.com/posting-api/job-board/{name_param}")
    out = []
    for j in raw.get("jobs", []):
        loc = j.get("location", "")
        out.append(normalize(
            company["name"], j.get("title"), loc,
            "remote" if j.get("isRemote") else None,
            j.get("jobUrl"), j.get("publishedAt"), j.get("descriptionPlain", ""),
        ))
    return out


def fetch_workday(company, fixtures_dir=None):
    tenant = company["tenant"]
    host = company.get("wd_host", "wd1")
    site = company.get("site", "External")
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    if fixtures_dir:
        raw = json.loads((fixtures_dir / "workday.json").read_text())
    else:
        raw = http_post(f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs", payload)
    out = []
    for j in raw.get("jobPostings", []):
        loc = j.get("locationsText", "")
        path = j.get("externalPath", "")
        out.append(normalize(
            company["name"], j.get("title"), loc,
            "remote" if "remote" in (loc or "").lower() else None,
            f"https://{tenant}.{host}.myworkdayjobs.com/{site}{path}" if path else None,
            j.get("postedOn"), "",
        ))
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}


def matches_filters(posting, extra_keywords):
    # Title only: description text is mostly company boilerplate (benefits,
    # EEO language) and matches domain keywords like "systems" too broadly.
    title = posting["title"].lower()
    if any(bad in title for bad in EXCLUDE_KEYWORDS):
        return False
    keywords = TITLE_KEYWORDS + [k.lower() for k in extra_keywords]
    return any(k in title for k in keywords)


def candidate_id(posting):
    key = f"{posting['company']}|{posting['title']}|{posting['location']}".lower().strip()
    return key


def posted_sort_key(posting):
    """Best-effort recency key across ATSes with different date formats.
    ISO8601 and epoch-ms parse to real timestamps; anything else (Workday's
    "Posted N Days Ago" strings) sorts after all parsed dates, oldest last."""
    raw = posting.get("posted")
    if isinstance(raw, (int, float)):
        return raw / 1000.0 if raw > 10**12 else raw
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", action="store_true", help="read from lanes/career/fixtures/*.json instead of live APIs")
    ap.add_argument("--home", default=os.environ.get("ORBIT_HOME", str(Path(__file__).resolve().parent.parent.parent)))
    ap.add_argument("--fire", default=os.environ.get("ORBIT_FIRE", "manual"))
    args = ap.parse_args()

    home = Path(args.home)
    companies_path = home / "config" / "lanes" / "career" / "companies.json"
    companies = json.loads(companies_path.read_text())

    fixtures_dir = Path(__file__).resolve().parent / "fixtures" if args.fixtures else None

    state_dir = home / "state" / "career"
    state_dir.mkdir(parents=True, exist_ok=True)
    seen_path = state_dir / "seen.json"
    seen = set(json.loads(seen_path.read_text())) if seen_path.exists() else set()

    per_company = {}
    manual_skipped = []
    errors = {}
    all_candidates = []

    for company in companies:
        ats = company.get("ats", "manual")
        if ats == "manual":
            manual_skipped.append(company["name"])
            continue
        fetcher = FETCHERS.get(ats)
        if fetcher is None:
            errors[company["name"]] = f"unknown ats: {ats}"
            continue
        try:
            postings = fetcher(company, fixtures_dir)
        except Exception as e:  # noqa: BLE001 — fail soft per company, never crash the run
            errors[company["name"]] = f"{type(e).__name__}: {e}"
            per_company[company["name"]] = 0
            continue

        extra = company.get("keywords_extra", [])
        kept = [p for p in postings if matches_filters(p, extra)]
        per_company[company["name"]] = len(kept)

        for p in kept:
            cid = candidate_id(p)
            if cid in seen:
                continue
            seen.add(cid)
            all_candidates.append(p)

    all_candidates.sort(key=posted_sort_key, reverse=True)
    all_candidates = all_candidates[:CANDIDATE_CAP]

    candidates_path = state_dir / f"candidates-{args.fire}.json"
    candidates_path.write_text(json.dumps(all_candidates, indent=2))
    seen_path.write_text(json.dumps(sorted(seen), indent=2))

    summary = {
        "ok": True,
        "companies_checked": len(companies),
        "per_company_new": per_company,
        "manual_skipped": manual_skipped,
        "errors": errors,
        "new_candidates": len(all_candidates),
        "candidates_file": str(candidates_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
