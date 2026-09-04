---
lane: sim
model: sonnet-5
effort: medium
max_turns: 40
dir: ~/git/orbit
---
# Sim drills — a question set per tagged lead

## Steps
1. Read `briefs/data/plan.md`; anything addressed to the sim wins.
2. Find leads with a `go` action and no `drill` items yet (`meta.lead` equals the lead id). For each (cap 2 per night), fetch the posting from the lead's `meta.url` when possible; otherwise use the lead's title, body, and the scored notes in `briefs/data/items/leads-*.md`.
3. Build the set exactly as `config/lanes/sim/LANE.md` describes: 3 behavioral, 2 systems, 2 domain, 1 curveball, each with one line on what a strong answer must contain. Write `briefs/data/items/drillset-<lead>-<date>.md`.
4. Emit each question: `python3 $ORBIT_HOME/system/emit.py item --kind drill --id drill-<lead>-<n>-<date> --title "<question, under 90 chars>" --body "<what a strong answer contains, one line>" --meta '{"lead": "<lead id>", "category": "<behavioral|systems|domain|curveball>", "question": "<full question>", "path": "briefs/data/items/drillset-<lead>-<date>.md"}'`
5. If no new tagged leads: emit one general drill (alternate systems design with the domain controller as the worked example, and a behavioral question from a story in the bank not yet drilled), `meta.lead: general`.
6. Copy this file back into `queue/500-sim-drills.md`, then the STATUS block.

## Constraints
- Never write model answers. The strong-answer line names what must be present, not the words.
