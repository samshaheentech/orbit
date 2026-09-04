---
lane: system
exec: lanes/system/plan.py
hours: 22
effort: low
dir: ~/git/orbit
---
# System plan — draft tomorrow at 22:00

## What this does
`lanes/system/plan.py` reads the queue, the last 24 hours of events, and your input in `briefs/data/plan.md`, then drafts tonight as a `plan_draft` event: queue order, light then heavy, your requests first, what the backlog should add. It never clears `plan.md`; the 07:40 brief does that after reading it.

## Cadence
Runs only in the 22:00 fire (`hours: 22` keeps it in the queue at other fires). Re-queues itself.

## Cost
One Sonnet 5 call for the prose; a deterministic draft if the call fails.
