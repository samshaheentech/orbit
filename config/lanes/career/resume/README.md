# Resume loop config

- `champion.md`: the current resume (v33) as markdown, extracted from the PDF with headings, bullets, and order preserved. Gitignored because it carries a phone number and the repo is public; it travels in the Fire 5 zip and lives in the working tree. If this file is missing, `queue/130-career-resume.md` blocks with the exact path.
- `rulings.md`: locked rulings from the mission file. Grader B disqualifies any challenger that breaks one. Add new ones under "Sam adds more here".
- `prompts/improver.md`, `prompts/grader_a.md`, `prompts/grader_b.md`: the three `claude -p` prompts. `{{POSTING}}`, `{{CHAMPION}}`, `{{CHALLENGER}}`, `{{EDITS}}`, `{{PROFILE}}`, `{{RULINGS}}` are filled by `lanes/career/resume_loop.py`. The improver template may only use the first two; the dry run asserts that.
- `approved/<lead-id>.md`: written when you press Approve on a challenger in the webapp. Also gitignored. A base-run approval lands as `approved/base-<date>.md` and does not replace `champion.md`; you do that by hand once you agree.

Replace the champion by overwriting `champion.md`. The next fire keeps grading against the new text; the champion item in the webapp keeps its id.

Mission file: add a line `Mission file: ~/path/to/Sam_Career_Mission.md` to `config/user.md` (or export `ORBIT_MISSION_FILE`) and approvals append a line to its "## Tailored variants" section.
