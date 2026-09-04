# Orbit for a new user

Written for Mike Linares and his Claude, and for anyone after him. Sam built Orbit for a job hunt; you will point it at your own work. The core is generic. Only the config and the lanes are Sam's.

## What you are getting
A scheduler (`run.sh` + launchd) that runs Claude Code tasks five times a day, an append-only log every task writes to, and a local webapp that turns the log into a morning brief, lane pages, a fires timeline, and a plan box. Read `README.md` first; it is short.

## Step 1: fork and clone
```bash
gh repo fork samshaheentech/orbit --clone   # or fork in the browser, then git clone your fork
cd orbit
```

## Step 2: what to replace, what to keep

Replace (Sam-specific):
- `config/user.md`: who you are, your goals, your accounts, your rubrics.
- `config/lanes/career/` and `queue/1*.md`: Sam's career lane. Delete them, or keep the folder as a worked example and delete the tasks.
- `config/lanes/research/topics.seed.json`: Sam's topics. Write yours.
- `launchd/*.plist` labels say `com.sam.*`; rename to yours or leave them, they are just labels.

Keep (generic, do not edit in your first week):
- `run.sh`, `server.py`, `system/emit.py`, `system/data-contract.md`, `system/prompt.md`, `system/estimate.py`, `system/window.py`, `system/assign.py`
- `lanes/system/` (plan, brief, retro), `queue/2*.md` and `queue/900-system-retro.md`
- `briefs/index.html`
- `install.sh`, `bin/orbit`

Probably keep and adapt:
- `config/lanes/operations/` (Gmail triage works for anyone; edit the taxonomy and accounts, follow `SETUP.md`)
- `config/lanes/research/` (digests and checks work for any subject; the coding ramp is optional, delete `310` if you don't code)

## Step 3: the questions your Claude should ask you
Sam answered these before anything was built. Answer them in a chat with your Claude, then have it write `config/user.md` and your lanes from `config/lanes/_TEMPLATE/`:

1. What buckets of work should it do every day? (Mike: content pipeline, nursing education research, brand and sponsorship leads, community questions, admin.)
2. What do you want waiting for you when you wake up?
3. Where do you read: the webapp, or something else?
4. Which numbers would you actually track and want to improve?
5. Which email accounts, and what does "clean" mean to you?
6. What is your daily plan input going to look like: a sentence, a list, nothing?
7. Is there a living document about your work the agent should own?
8. How much of your Claude plan are you willing to spend per day?

## Step 4: install
```bash
bash install.sh          # launchd jobs, server, orbit CLI
orbit status
orbit open
```

## Step 5: first tasks
Copy `config/lanes/_TEMPLATE/` to `config/lanes/<yourlane>/`, write `LANE.md`, then `orbit add 100-<yourlane>-<name>` for each task. Run `orbit fire` once by hand and read the report in the webapp before you let the schedule run.

## What we learned building it, so you don't pay for it twice
- Build fires in a fresh chat, one fire per chat, from a handoff file (`docs/handoffs/`). A long chat taxes every message.
- Sonnet for lanes and scaffolding, Fable for judgment and UI, Haiku for mechanical work. The `model:` line in each task is where that lives.
- Report your usage meter after every fire. The estimator (`orbit estimates`) learns from real numbers only.
- Produced vs consumed is the health metric. If the webapp shows more than you read, cut volume before adding lanes.
- Nothing destructive without a gate: the operations lane needs your approval and 14 days before it trashes anything, the retro applies changes on a branch.
