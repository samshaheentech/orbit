# Fire 5 handoff: blind resume loop

Built 2026-09-03. Scope came from the Fire 5 handoff; nothing re-proposed.

## What exists now

- `run.sh` understands `exec: <path>` in task frontmatter: runs `python3 <path>` from `ORBIT_HOME`, captures stdout as the result, same timeout, same `task_start`/`task_end` events. Skips the git worktree for exec tasks. Reads an optional `COST_USD: <n>` line from the script so spend by lane stays honest.
- `lanes/career/resume_loop.py`: the orchestrator. Stdlib, Python 3.9. Three separate `claude -p` processes per job, `--tools ""` so none of them can read a file even if asked. Graders run concurrently as separate processes; the improver never gets `config/user.md`, `rulings.md`, or anything but `improver.md` + `champion.md` + the posting text, and `--dry-run` proves it two ways (no profile/rulings line in the prompt; every prompt line traces to one of the three sources).
- `config/lanes/career/resume/`: `champion.md` (v33 from the PDF, gitignored, in the zip), `rulings.md`, `prompts/`, `README.md`, and `approved/` (created on first approval, gitignored).
- `queue/130-career-resume.md`: daily exec task; the script copies it back into `queue/` on DONE.
- `lanes/career/fixtures/resume/`: one posting, one improver output, one grader A output, two grader B outputs (pass, violation). Dry run job 1 surfaces, job 2 discards, `--force-base` adds a base job that surfaces.

## Decisions worth knowing

- Attempts: a posting with a surfaced or discarded outcome is never re-run. A posting that errored (claude down, bad JSON) gets one more try, then it is done. Base runs key on ISO week.
- Approval of a base challenger copies the resume to `approved/base-<date>.md` and says "approved base challenger, promote by replacing champion.md" in the STATUS notes. Sam promotes by hand.
- Mission file path: `Mission file: <path>` line in `config/user.md`, or `ORBIT_MISSION_FILE`. Not configured yet; approvals say so in Notes and still write the approved copy.
- Every claude call: `--model`, `--output-format json`, `--permission-mode dontAsk`, `--tools ""`, `--max-turns 1`, `--no-session-persistence`. Code fences stripped before `json.loads`; if the result is not an object the job errors rather than guessing.
- `champion.md` as extracted contains 15 em-dashes and does not open with the Bosch record, so it breaks rulings 1 and 2 as written. The improver cannot know the rulings, so grader B will disqualify most challengers until the champion complies or the rulings are relaxed. Open question for Sam.

## Verify

```bash
bash -n run.sh
python3 lanes/career/resume_loop.py --dry-run --force-base
```

## Fire 6

Research and learning lane: digests, coding ramp, knowledge profile. The data contract already names the kinds (`digest`, `problem`, `profile`).
