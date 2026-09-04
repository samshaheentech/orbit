---
lane: operations
model: sonnet-5
effort: medium
max_turns: 30
dir: ~/git/orbit
---
# Career mission file — keep it current

## Goal
`config/lanes/career/mission.md` is the living record of Sam's job hunt, owned by the agent, gitignored because it is personal.

## Steps
1. If the file is absent, create it from `config/user.md` plus what the log knows: sections Mission, Targets (from `companies.json` and `add_target` actions), Applications (leads tagged `go`, with state: tagged, tailored, applied when Sam says so in `plan.md`), Resume (champion version, approved variants under `config/lanes/career/resume/approved/`), Open items, Log (dated one-liners). Add at the top: "Sam: paste your current Sam_Career_Mission.md sections into these headings once; from then on the agent maintains it." Emit `meta.question` on the mission item asking him to do that.
2. Otherwise update only the sections that changed since the file's last date, from the log: new `go` leads into Applications, approved resume variants into Resume, anything from `plan.md` addressed to the mission file, blocked career tasks into Open items. Append one dated line to Log per run. Never rewrite Sam's own prose; add below it.
3. Emit (update in place): `python3 $ORBIT_HOME/system/emit.py item --kind mission --id mission-file --title "Sam_Career_Mission" --body "<one line: what changed>" --meta '{"updated": "<date>", "path": "config/lanes/career/mission.md"}'`
4. Copy this file back into `queue/420-ops-mission.md`, then the STATUS block.

## Constraints
- Nothing speculative. If the log does not say it happened, it is not in the file.
