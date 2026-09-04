---
lane: sim
model: fable-5-1
effort: medium
max_turns: 30
weight: heavy
dir: ~/git/orbit
---
# Sim grade — every answer Sam submitted, against the posting

## Steps
1. Find `item_action` events with `action: answer` on `drill` items that have no `feedback` item yet (`meta.drill` equals the drill id). If none, report DONE with "no answers pending" and re-queue.
2. For each: read the drill, its set file, the posting notes for its lead, the story bank, and any canon stories. Grade per the rubric in `config/lanes/sim/LANE.md`: score 1 to 5, what landed, what was missing that the bank had, what to cut for 90 seconds, and one sentence Sam could say instead.
3. Write `briefs/data/items/feedback-<drill id>.md` and emit: `python3 $ORBIT_HOME/system/emit.py item --kind feedback --id feedback-<drill id> --title "<drill question, under 90 chars>" --body "<score>/5: <the one sentence to say instead>" --meta '{"drill": "<drill id>", "score": <n>, "landed": "<..>", "missing": "<..>", "cut": "<..>", "path": "briefs/data/items/feedback-<drill id>.md"}'`
4. Update the drill: `emit.py update --id <drill id> --patch '{"meta": {"score": <n>}}'`. Under 4: also `{"meta": {"retry": "<date + 7 days>"}}`; the drills task re-serves it then.
5. Copy this file back into `queue/520-sim-grade.md`, then the STATUS block with the count graded and the average.

## Constraints
- Grade the answer that was given, not the answer you would give. The "say instead" line is the only place your version appears.
