---
lane: <lane>
model: sonnet-5
effort: medium
max_turns: 40
dir: ~/git/orbit
# days: sun
# hours: 22
# weight: heavy
# requires_mcp: <server name>
---
# <Task title>

## Goal
What should be true when this run is done.

## Steps
1. Read `briefs/data/plan.md`; honor anything addressed to this lane.
2. ...
3. Emit results: `python3 $ORBIT_HOME/system/emit.py item --kind <kind> --id <kind>-<slug>-<date> --title "..." --body "..." --meta '{...}'`
4. Copy this file back into `queue/<this file>`, then the STATUS block.

## Constraints
- Emit only what earns its place; produced vs consumed is the health metric.
