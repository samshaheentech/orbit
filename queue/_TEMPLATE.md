---
lane: career          # career | research | operations | system
model: sonnet-5       # sonnet-5 | fable-5-1 | haiku-4-5
effort: medium        # low | medium | high | max
max_turns: 60
tools:                # extra shell allowlist beyond defaults (optional)
# exec: lanes/x/y.py  # run a script directly instead of claude -p (optional)
# days: sun,wed       # only run on these days (optional)
# hours: 22           # only run in these fires, local hour (optional)
# weight: heavy       # heavy tasks run last in a fire and are skipped right after a usage limit (optional)
# requires_mcp: gmail # skip (and log blocked) until `claude mcp list` shows a server with this name (optional)
dir: ~/               # working directory
---
# Task title

## Goal
What should be true when this is done.

## Done means
- Specific checkable condition
- Another checkable condition

## Context
Where to look, what exists, decisions already made.

## Constraints
- Any hard limits
