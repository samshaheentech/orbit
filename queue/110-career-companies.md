---
lane: career
model: fable-5-1
effort: medium
max_turns: 60
tools:
dir: ~/git/orbit
---
# Career companies — propose new targets

## Goal
Five companies not already in `config/lanes/career/companies.json`, where Sam's profile (7 years Bosch ADAS, embedded, senior, robotics/autonomy/aerospace/AI-infra leaning) meets where the world is moving.

## Done means
- Read `config/lanes/career/companies.json` and every `company` item and its actions already in the log — never repeat a company already there, tagged `prune`d, or already proposed and still open.
- Exactly 5 new companies proposed, each emitted as a `company` item with: name, domain (one line, what they do), why the profile maps (one line, specific to Sam — not generic "growing company"), a real careers URL (verify it resolves — a plausible-looking URL that 404s doesn't count), one risk (why this might not pan out: funding, market, level fit, whatever's true).
- `companies.json` is NOT edited — that's the leads task's job, triggered by Sam tagging `add_target`.
- This file is copied back into `queue/` so next Sunday's fire picks it up.
- STATUS block includes the 5 names and confirmation each URL was checked.

## Context
- Read `config/lanes/career/LANE.md` and `config/user.md` first.
- Read `briefs/data/plan.md` for anything addressed to the career lane before proposing.
- Emit each as, e.g.:
  ```bash
  python3 "$ORBIT_HOME/system/emit.py" item --kind company --id company-relativity-space-2026-09-07 \
    --title "Relativity Space — 3D-printed rockets and reusable launch" \
    --body "Embedded/avionics-heavy, senior ADAS background maps to flight software and vehicle systems. Risk: launch cadence has slipped before." \
    --meta '{"domain":"relativityspace.com","url":"https://www.relativityspace.com/careers"}'
  ```
- Bias toward companies where a senior embedded engineer's actual skills (real-time systems, safety-critical software, hardware/software integration) are the hiring need, not a stretch.

## Constraints
- Only run shell commands whose prefix is in the allowlist (`python3`, `curl`, `jq`, `git`, `ls`, `cat`, `find`, `wc`) — use `curl` to check a careers URL resolves (`curl -sI -o /dev/null -w '%{http_code}' <url>`), don't fabricate a URL you haven't checked.
- Never edit `companies.json` directly.
- Never send email, never apply to anything, never push.
