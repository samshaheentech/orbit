# Orbit

**Mission control for your life.** A personal agent platform that runs on your Mac, works a task queue five times a day with Claude Code, and delivers a morning brief into a local dark-mode webapp. Apollo, the voice layer, comes later.

Built by Sam Shaheen, for a job hunt first. The core is generic; a new user replaces the config and the lanes (`docs/SETUP-NEW-USER.md`).

## In two minutes

- **Windows.** Orbit owns two 5-hour windows a night, 22:00 and 03:00 (`config/schedule.json`). launchd polls every 15 minutes; inside a window with budget and time left, the runner works the queue light-first, then heavy, then pulls from `backlog/`. Each window spends up to 50% of its capacity, measured through a calibration you feed by typing the meter reading once or twice. The plan is drafted at 22:00 and the brief lands at 07:40. Daytime is yours; `orbit fire` runs a manual fire any time.
- **Tasks.** A task is a markdown file in `queue/` (or `backlog/` for one-shots that run when budget is spare) with frontmatter (`lane`, `model`, `effort`, `days`, `hours`, `weight`, `exec`, `requires_mcp`) and a body that briefs the agent. Recurring tasks copy themselves back into the queue.
- **One log.** Everything lands in `briefs/data/events.jsonl`: fires, tasks, items the lanes produce, and every action you take in the webapp. `system/data-contract.md` is the schema; lanes write through `system/emit.py`.
- **Webapp.** `localhost:4242`, always on. The orbit ring, the brief with history, lane pages with actions, the fires timeline, spend by lane and model, ratings, your plan input.
- **Lanes.** Career (leads from real job boards, blind resume loop, company discovery, ideas), Research (digests with checks, coding ramp, knowledge profile), Sim (question sets per tagged lead, STAR drafts, your answers graded overnight, dictation), Operations (Gmail triage with a modify-only token, deletions behind a 14-day gate, mission file), System (plan, brief, retro).
- **Cost.** Every run records tokens and cost; an estimator learns from history; the brief shows spend and estimate accuracy; heavy tasks pause for a window after a usage limit.
- **Self-improvement.** Sunday retro proposes exact edits to its own tasks and prompts; you approve in the webapp; applied on a branch, never `main`.

## Install
```bash
git clone https://github.com/samshaheentech/orbit ~/git/orbit
bash ~/git/orbit/install.sh
orbit status
```
Desktop app (optional, same UI in a native window with a menu bar countdown and notifications): `bash desktop/build.sh`.

Requires macOS, Node 22+, Python 3, Claude Code logged in (`npm install -g @anthropic-ai/claude-code`, `claude login`), a Claude Max plan. Gmail is optional: `config/lanes/operations/SETUP.md`.

## Daily use
```bash
orbit brief          # the latest brief, in the terminal
orbit add 100-x      # new task from the template
orbit fire           # run a fire now
orbit status         # next fire, queue, last fire, window, server
orbit pause / resume # the schedule
orbit estimates      # estimate accuracy
orbit assign         # which tasks earn a cheaper or better model
```
Write anything for the next fire in the Plan page; the 02:00 brief reads it and clears it.

## Layout
```
run.sh              the runner            server.py         the webapp server
bin/orbit           the CLI               install.sh        one-time install
briefs/index.html   the webapp            briefs/data/      the log and item files (gitignored)
system/             contract, emitter, estimator, window, assignments, system prompt
lanes/<lane>/       lane scripts          config/lanes/<lane>/   lane config, prompts, rules
queue/              tasks                 config/user.md    who you are
docs/handoffs/      how each fire was specified
```

## Safety rules that are built in
No sends from Gmail (the token has no send scope). Nothing trashed without your approval plus 14 days. No pushes, no `main` commits by any task. Resume improvements only surface if two independent graders agree. Every Gmail call is audit-logged.

## Build history
Fire 1 skeleton, 2 webapp shell, 3 contract and live data, 4 career lane, 5 blind resume loop, 6 brief engine and research lane, 7 operations lane, 8 token intelligence, 9 retro, CLI, new-user docs. Specs in `docs/handoffs/`.

## Status
All nine fires done. Next: run it for a week, read the retro, then Apollo.
