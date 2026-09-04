---
lane: sim
model: sonnet-5
effort: medium
max_turns: 30
dir: ~/git/orbit
---
# Sim stories — one STAR draft a night

## Steps
1. Read `config/lanes/sim/stories.json`. Pick the first story with `status: bank` that has no `story` item, or one with a `skip` action and a note in `plan.md` asking for changes.
2. Write `briefs/data/items/story-<slug>.md`: Situation, Task, Action, Result in full, with real numbers from `config/user.md` and the mission file where they exist and placeholders like `[number]` where they don't, then a "Say it in 90 seconds" version under 220 words, first person, no em-dashes.
3. Emit: `python3 $ORBIT_HOME/system/emit.py item --kind story --id story-<slug> --title "<story title, under 90 chars>" --body "<the first sentence of the spoken version>" --meta '{"slug": "<slug>", "path": "briefs/data/items/story-<slug>.md"}'`
4. Set the story's `status` to `drafted` in `stories.json`; an `approve` action seen on a later run sets it to `canon`.
5. Copy this file back into `queue/510-sim-stories.md`, then the STATUS block.

## Constraints
- Invent nothing. A placeholder is better than a made-up number.
