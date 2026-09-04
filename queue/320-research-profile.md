---
lane: research
model: fable-5-1
effort: medium
max_turns: 30
days: sun
dir: ~/git/orbit
---
# Knowledge profile — Sundays, evidence only

## Goal
Update what Orbit believes about Sam's strengths and gaps, from evidence only, and reprioritize the topic list from the gaps.

## Steps
1. Read the log for `item_action` with `action: check` (score in `result`), `problem` items and their status updates (passed, struggled, retention passes), and digests read (`read` actions).
2. Read existing `profile` items. Each line must trace to an id in `meta.evidence`.
3. Emit new lines or updates: `emit.py item --kind profile --id profile-<slug> --title "<claim, under 90 chars>" --meta '{"side": "strength"|"gap", "evidence": "<item or check id>"}'`; a gap that closed gets `emit.py update --id profile-<slug> --patch '{"meta": {"closed": "<date>"}}'`. Never delete.
4. Rewrite priorities in `state/research/topics.json`: gaps up, closed gaps down, and add up to 2 new topics if the evidence points somewhere the list lacks.
5. Copy this file back into `queue/320-research-profile.md`, then the STATUS block.

## Constraints
- No line without evidence. "Seems strong at X" is not a line.
- Keep the profile under 20 lines total across both sides.
