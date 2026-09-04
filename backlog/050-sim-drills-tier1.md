---
lane: sim
model: sonnet-5
effort: medium
max_turns: 40
dir: ~/git/orbit
---
# Sim: question sets for Tier 1 targets without a tagged lead

## Goal
Sam should not meet NVIDIA, Waymo, Qualcomm, Zoox, Apple, or Google cold. For each Tier 1 company in `config/lanes/career/companies.json` with no `drill` items, build an eight-question set from that company's public interview reports and its current postings closest to Sam's profile, exactly as `config/lanes/sim/LANE.md` describes, `meta.lead: <company slug>`.

## Steps
Follow `queue/500-sim-drills.md` steps 3 and 4 per company, cap 2 companies per run, then the STATUS block. Do not re-queue.
