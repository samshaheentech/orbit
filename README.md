# Orbit

**Mission control for your life.**

Orbit is a personal AI agent platform that runs on your Mac, works a task queue while you sleep, and delivers a morning brief into a local dark-mode webapp. Talk to it by voice through Apollo (coming soon).

## What it does

- Fires 5x/day on a schedule (10pm planning, 2am morning brief, 6am/2pm/6pm working fires)
- Works your task queue using Claude Code headless mode
- Delivers briefs, job leads, research digests, coding problems, and business ideas
- Tracks token usage and learns which model fits which task
- Self-improves weekly via a Sunday retro fire

## Install

```bash
git clone https://github.com/samshaheentech/orbit ~/git/orbit
bash ~/git/orbit/install.sh
```

Requires: macOS, Node.js, Claude Code CLI (`npm install -g @anthropic-ai/claude-code`), Claude Max plan.

## Add a task

```bash
cp ~/git/orbit/queue/_TEMPLATE.md ~/git/orbit/queue/010-my-task.md
# edit the file, then the next fire picks it up
```

## View your brief

Open `http://localhost:4242` in any browser. Always running on login.

## Status

- Fire 1 — skeleton: runner, server, event log, launchd, plugin layout. Done.
- Fire 2 — webapp UI shell: orbit ring, telemetry, lanes, fires timeline, plan input. Done.
- Fire 3a — data contract, emitter, live lane/brief/plan rendering. Done.
- Fire 3b — actions (tag, skip, explore, prune, approve, read), produced vs consumed, spend by lane and model. Done.
- Fire 3c — brief history, per-lane archive, fires filter. Done.
- Fire 4 — career lane. Next.

## Architecture

- `run.sh` — core runner, called by launchd
- `server.py` — local webapp server (stdlib Python, no deps)
- `briefs/` — webapp and event log
- `config/user.md` — your config (name, goals, targets, rubrics)
- `config/lanes/` — one folder per lane (career, research, operations...)
- `queue/` — tasks waiting to run
- `launchd/` — macOS scheduler plists
- `system/prompt.md` — system prompt appended to every agent run
- `system/data-contract.md` — the event shapes lanes write; read this before writing a lane
- `system/emit.py` — how lanes deliver items, briefs, and plan drafts

## Voice (coming soon)

Apollo — talk to Orbit like Tony Stark talks to Jarvis.

## For contributors

Clone the repo, fill in your own `config/user.md`, define your lanes. The core is generic — it knows nothing about you until you configure it.
