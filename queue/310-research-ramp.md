---
lane: research
model: sonnet-5
effort: medium
max_turns: 40
tools: Bash(python3 lanes/research/ramp_check.py *)
dir: ~/git/orbit
---
# Coding ramp — check, hint, keep two open

## Goal
Sam always has two problems open on the roadmap, his struggles come back with a hint, his passes come back a week later.

## Steps
1. Run `python3 lanes/research/ramp_check.py --json` and read the summary. It has already updated `meta.json` files and emitted status updates.
2. For each `struggled` entry with `hints` under 2: append one hint to that problem's README under `## Hint <n>` (a nudge toward the pattern, never code), bump `hints` in `meta.json`.
3. If `open_count` is under 2, create the next problem on the roadmap in `config/lanes/research/LANE.md`, skipping slugs that already exist in `ramp/`. Files: `README.md`, `solution.py` (signature and `pass` only), `test_<slug>.py` (plain asserts, exits non-zero on failure), `meta.json` with `id` `problem-<slug>-<date>`, `slug`, `pattern`, `status: open`, `due` two days out, `signature`, `hints: 0`. Emit: `python3 $ORBIT_HOME/system/emit.py item --kind problem --id problem-<slug>-<date> --title "<Problem name>" --body "<one line: the pattern and what it trains>" --meta '{"pattern": "<pattern>", "status": "open", "due": "<yyyy-mm-dd>", "path": "ramp/<slug>/README.md"}'`
4. Copy this file back into `queue/310-research-ramp.md`, then the STATUS block with the summary numbers.

## Constraints
- Never write code in `solution.py` beyond the signature. Never put a solution in a hint.
- Start of the roadmap for Sam: hash maps (Two Sum is done; Valid Anagram is open in his own files, recreate it here as the first problem if `ramp/` is empty), then Group Anagrams, then two pointers.
