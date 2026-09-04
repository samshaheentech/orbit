---
lane: career
model: sonnet-5
effort: medium
max_turns: 60
tools:
dir: ~/git/orbit
---
# Career leads — fetch, score, emit

## Goal
Every Tier 1/2 company in `config/lanes/career/companies.json` gets checked for new postings today, scored against Sam's profile, and the good ones show up as `lead` items in the brief.

## Done means
- `state/career/candidates-<fire>.json` exists from a fresh `fetch_jobs.py` run this fire.
- Every candidate is scored per `config/lanes/career/scoring.md`.
- A `lead` item is emitted for every posting scoring 60+.
- The full scored table (every candidate, including sub-60) is written to `briefs/data/items/leads-<date>.md`.
- If `briefs/data/plan.md` has anything addressed to the career lane, it's read and honored before scoring (e.g. "skip defense companies this week").
- If any `item_action` with `add_target` exists in the log for a `company` item not already in `companies.json`, look up its real ATS and append it to `companies.json` (commit the change).
- This file is copied back into `queue/` so tomorrow's fire picks it up (see `config/lanes/career/LANE.md` "Recurrence").
- STATUS block includes: fetched (companies checked), new (candidates found), scored (count), emitted (count 60+).

## Context
- Read `config/lanes/career/LANE.md`, `config/lanes/career/scoring.md`, `config/user.md` first.
- Fetcher: `python3 lanes/career/fetch_jobs.py --home "$ORBIT_HOME"` (no `--fixtures` — this is a real run). It fails soft per company; a company erroring or `manual` isn't a blocker, just note it in the STATUS report.
- Score every entry in the candidates file against `config/lanes/career/scoring.md`'s rubric, using `config/user.md` for Sam's specifics.
- Emit each 60+ lead with the emitter, e.g.:
  ```bash
  python3 "$ORBIT_HOME/system/emit.py" item --kind lead --id lead-anduril-staff-infra-2026-09-04 \
    --title "Anduril, Staff Systems Engineer, Perception Infrastructure" \
    --body "Fully remote, staff level, perception infra for autonomy platforms. Score 88." \
    --meta '{"score":88,"company":"Anduril","url":"https://...","comp":"230-300k","remote":"remote"}'
  ```
- Write the full table (all scored postings, sub-60 included, with score/dims/reason) to `briefs/data/items/leads-<yyyy-mm-dd>.md` as a markdown table so Sam can see what got filtered and why.
- Update `briefs/data/plan.md`'s open-items only if this run changed something plan.md was asking about — don't touch it otherwise.

## Constraints
- Never mark your own items read.
- Only emit what earns its place — don't emit a `lead` for anything under 60, even if `companies.json` only has a few live candidates today.
- Shell prefixes limited to the `run.sh` allowlist: `python3`, `curl`, `jq`, `git`, `ls`, `cat`, `find`, `wc`.
- Never send email, never apply to anything, never push.
