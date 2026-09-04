---
lane: career
model: sonnet-5
effort: medium
max_turns: 40
dir: ~/git/orbit
---
# Company deep dive: Waymo

## Goal
One page Sam can read in ten minutes before any Waymo conversation: what the onboard platform org ships now, team structure as far as public sources show, the interview loop as reported publicly, three people worth knowing about, and the five things in Sam's background that map to their current priorities.

## Steps
1. Search the web for current Waymo news, job postings, engineering blog posts, and interview reports from the last 12 months.
2. Write `briefs/data/items/company-waymo-<date>.md`.
3. Emit a `company` item with `meta.domain: autonomy platform`, `meta.url`, `meta.path`, and `meta.question: "Anything here you want turned into drills?"`.
4. STATUS block. Do not re-queue.
