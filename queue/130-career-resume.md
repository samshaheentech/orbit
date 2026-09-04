---
lane: career
exec: lanes/career/resume_loop.py
model: fable-5-1
effort: medium
dir: ~/git/orbit
---
# Career resume — blind challenger loop

## Goal
Every lead Sam tagged `go` gets one tailored challenger resume, produced by a process that cannot flatter him: a blind improver, two informed graders that never see each other, and a decision rule that discards anything that is not clearly better and fully compliant. Once a week, on Sunday, the same loop runs with no posting at all.

## What runs
`run.sh` sees `exec:` and runs `python3 lanes/career/resume_loop.py` from `ORBIT_HOME` instead of wrapping this file in `claude -p`. The script:

1. Blocks with the exact path if `config/lanes/career/resume/champion.md` is missing.
2. Emits the champion item `resume-champion-v33` once, ever.
3. Finds every `lead` with a `go` action and no challenger yet (newest, highest score first, at most 3 per run, never the same posting twice; attempts in `state/career/resume-attempts.json`). On Sundays adds one base run with a generic target.
4. For each: fetches the posting from `meta.url` (plain urllib, fails soft to the lead's title, body, and the scored row in `briefs/data/items/leads-<date>.md`), then runs three separate `claude -p` processes, no tools, one turn each:
   - improver, `claude-fable-5-1`, sees champion + posting only, returns `{"resume_md", "edits"}`;
   - grader A, `claude-sonnet-5`, and grader B, `claude-fable-5-1`, each see champion, challenger, posting, `config/user.md`, `rulings.md`; each returns per-dimension scores for both documents, 0 to 100, plus `violations`.
5. Surfaces the challenger only if both graders score it at least 5 above the champion and grader B lists zero violations: writes `briefs/data/items/resume-<lead-id>-<date>.md` and emits a `resume` item (`status` challenger, `version` v33+n, `graders` {a, b}, `posting`, `path`). Otherwise discards it and writes scores and reason to `state/career/resume-log.jsonl`. Every attempt, either way, is logged there.
6. Processes approvals: a challenger with an `approve` action is copied to `config/lanes/career/resume/approved/<lead-id>.md` and, if a mission file is configured, a line is appended to its tailored-variants section. A base-run approval is copied but does not replace the champion; the STATUS notes say so.
7. Copies this file back into `queue/` on DONE, so tomorrow's fire picks it up.

## Done means
- STATUS block lists jobs run, surfaced, discarded, errors, approvals, and a `COST_USD:` line.
- Nothing reached the webapp that both graders did not clear.
- This file is back in `queue/`.

## Verification by hand
```bash
cd ~/git/orbit
python3 lanes/career/resume_loop.py --dry-run --force-base
```
Runs on fixtures under `lanes/career/fixtures/resume/`, writes only under `state/career/resume-dryrun/`, and prints the blindness proof and the decision self-test.

## Constraints
- Stdlib only. No tools inside any `claude -p` call. Never edits `champion.md`. Never sends anything anywhere.
