---
lane: career
model: sonnet-5
effort: medium
max_turns: 60
tools:
dir: ~/git/orbit
---
# Career ideas — business concepts

## Goal
Three business ideas seeded from Sam's profile and the bench-orchestration startup concept, each with a why-now and a kill test.

## Done means
- Read every prior `idea` item and its actions in the log first. Never repeat a `prune`d idea. If an `explore`d idea exists, the next idea in that space should build on it (reference it in the body), not restate it.
- Exactly 3 `idea` items emitted, each with `meta.why_now` and `meta.kill_test`.
- One idea should default to the bench-orchestration space (embedded hardware bench orchestration: reservation, state management, CI/CD integration, AI validation endgame) unless that space is already saturated with open (non-pruned) ideas — in that case, build on the strongest one instead of adding a fourth variant.
- The other ideas draw from Sam's actual background: 7 years embedded ADAS at Bosch, safety-critical systems, hardware/software integration, the same instincts that make him a strong senior candidate.
- This file is copied back into `queue/` so tomorrow's fire picks it up.
- STATUS block lists the 3 idea titles and whether each is new or builds on a prior one.

## Context
- Read `config/lanes/career/LANE.md` and `config/user.md` first.
- Read `briefs/data/plan.md` for anything addressed to the career lane before proposing.
- Kill test = the cheapest experiment that would disprove the idea, not "build an MVP." One sentence, concrete, executable in a weekend.
- Why-now = the specific market/technical shift that makes this the right moment, not a generic "AI is big now."
- Emit each as, e.g.:
  ```bash
  python3 "$ORBIT_HOME/system/emit.py" item --kind idea --id idea-bench-reservation-2026-09-04 \
    --title "Bench-as-a-service: reserve embedded test rigs like CI runners" \
    --body "CI/CD for hardware-in-the-loop. Teams burn hours coordinating shared bench access over Slack." \
    --meta '{"why_now":"CI/CD maturity in embedded teams has outpaced their bench tooling, still spreadsheet-and-Slack.","kill_test":"Cold-email 5 embedded eng managers asking how they schedule shared HIL benches today; if none say it hurts, kill it."}'
  ```

## Constraints
- Only run shell commands whose prefix is in the allowlist (`python3`, `curl`, `jq`, `git`, `ls`, `cat`, `find`, `wc`).
- Never send email, never apply to anything, never push.
