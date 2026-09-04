---
lane: research
model: sonnet-5
effort: medium
max_turns: 40
dir: ~/git/orbit
---
# Research digest — one topic a day

## Goal
One digest Sam will actually read, on the topic that best serves his targets this week, with a check at the end so the knowledge profile can learn from it.

## Steps
1. Read `briefs/data/plan.md`; if Sam named a topic for research, that topic wins.
2. If `state/research/topics.json` is missing, copy `config/lanes/research/topics.seed.json` there.
3. Pick the topic: highest priority with no completed check (an `item_action` with `action: check` on a digest whose id contains the slug), bumped if it touches a lead tagged `go` in the last 7 days.
4. Write `briefs/data/items/digest-<slug>-<date>.md`: 15 to 25 minutes of reading (about 1,500 to 2,500 words), concrete, no filler, written for a senior embedded engineer, tied to why it matters for his targets. End with the `## Check` block exactly as `config/lanes/research/LANE.md` specifies, answers comment last.
5. Emit: `python3 $ORBIT_HOME/system/emit.py item --kind digest --id digest-<slug>-<date> --title "<title>" --body "<one line on what it covers and why now>" --meta '{"minutes": <n>, "path": "briefs/data/items/digest-<slug>-<date>.md", "check": 5}'`
6. Set `last_written` on the topic in `topics.json`.
7. Copy this file back into `queue/300-research-digest.md`, then the STATUS block.

## Constraints
- No solutions to ramp problems, ever, even as examples.
- One digest per run. If today's digest already exists, report DONE with "already written" and re-queue.
