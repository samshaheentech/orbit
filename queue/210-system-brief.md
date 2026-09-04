---
lane: system
exec: lanes/system/brief.py
hours: 7
effort: low
dir: ~/git/orbit
---
# System brief — the morning brief at 07:40

## What this does
`lanes/system/brief.py` builds the brief from everything since the last one: what finished (each task's Changed line), what's new to read, questions for you (items with `meta.question`, blocked tasks), and tomorrow from the latest plan draft. Emits one `brief` event, then archives your `plan.md` input as a `plan_consumed` event and clears the file.

## Cadence
Runs only in the poll after 07:40 (`hours: 7`). Re-queues itself.

## Cost
One Sonnet 5 call to tighten the lines; raw lists if it fails.
