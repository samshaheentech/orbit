---
lane: system
exec: lanes/system/retro.py
days: sun
hours: 22
effort: medium
dir: ~/git/orbit
---
# Weekly retro — Sundays at 22:00

## What this does
`lanes/system/retro.py` reads the week (tasks, cost by lane and model, produced vs consumed, estimate accuracy, model assignment analysis, every action you took) and asks Fable for at most five concrete proposals: each is one exact find/replace in a task file, a lane config, a prompt, or a lane script. They appear as `proposal` items in the System section of your Brief page with Approve and Skip.

Approved proposals are applied the following Sunday on branch `orbit/retro-<date>`, committed one per proposal, never on `main`. Review with `git diff main..orbit/retro-<date>` and merge or delete. A proposal that fails to apply is marked failed with the reason and never retried.

## Cadence
Sundays only (`days: sun`, `hours: 22`). Re-queues itself.
