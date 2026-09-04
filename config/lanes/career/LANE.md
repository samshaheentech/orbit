# Career lane

## Goal
Land a remote senior/staff role by end of September 2026. Surface every posting worth Sam's attention, scored against `config/user.md`, before Sam ever has to search himself. Keep the target list alive — companies get added and postings get fetched daily, not researched from scratch each time.

## Sources
- `config/lanes/career/companies.json` — the target list, one entry per company with its ATS.
- Public ATS APIs (Greenhouse, Lever, Ashby, Workday) via `lanes/career/fetch_jobs.py`. No scraping, no login, no API keys.
- `manual` companies (no public API — Apple, Google, and any company where the fetcher can't confirm a live token) are skipped by the fetcher and listed in its run summary; a lane task can spot-check these by reading `config/lanes/career/companies.json` for the `url` field, but automated fetching is out of scope until they get a real token.

## Scoring
See `scoring.md` for the full rubric. Five dimensions, 0-20 each, 0-100 total. Hard filters zero a posting outright (see below). Emit only postings scoring 60+.

## Hard filters (score = 0, do not emit)
- Relocation required, no remote or hybrid option.
- Below senior level (new grad, junior, mid without senior/staff/principal in title).
- Stated comp ceiling under $150k base.

## Cadence
- `100-career-leads.md` — daily. Fetch, score, emit leads.
- `110-career-companies.md` — weekly, Sunday. Propose new targets.
- `120-career-ideas.md` — daily. Business ideas, independent of the job search but sharing the lane's cadence and cost budget.

## Cost caps
- Fetcher: stdlib only, no paid APIs, fails soft per company, capped at 30 new candidates per run.
- Tasks: `effort: medium`, default `max_turns: 60` from `run.sh`.

## Recurrence
`run.sh` moves a finished task to `done/` and does not re-add it. A task that should keep running copies its own file back into `queue/` as the last step before its `STATUS:` block, e.g.:

```bash
cp "$TASK_FILE" "$ORBIT_HOME/queue/100-career-leads.md"
```

`$TASK_FILE` is the path given in the task prompt (it points at `running/<name>.md` while the agent works, but the agent should read the *original* body from the copy `run.sh` moved into `running/` and write a clean copy — same frontmatter, same body, no `## Agent report` footer — back into `queue/`). Do this last, after all other work and after STATUS is decided, so a blocked or errored run doesn't silently requeue a broken task (`run.sh` already requeues `PARTIAL`/`ERROR` on its own; a self-copy is only needed for `DONE`, so the task doesn't stop recurring once it succeeds).

## New target companies
`110-career-companies.md` emits `company` items for review; it never edits `companies.json`. When Sam tags one `add_target`, `100-career-leads.md` reads that action on its next run, looks up the company's real ATS, and appends it to `companies.json` itself.
