# Career lead scoring rubric

Score every posting in `state/career/candidates-<fire>.json` against Sam's profile in `config/user.md`. One JSON object per posting, on one line each (JSONL), in this exact shape:

```json
{"id": "lead-nvidia-drive-2026-09-04", "company": "NVIDIA", "title": "Senior Software Engineer, DRIVE platform integration", "url": "https://...", "score": 92, "dims": {"prestige": 18, "purpose": 17, "remote": 20, "comp": 19, "trajectory": 18}, "reason": "Tier 1, DRIVE Thor stack, remote US, $215-290k, team scaling for 2027 launch.", "comp": "215-290k", "remote": "remote"}
```

`id` = `lead-<company-slug>-<yyyy-mm-dd>` (today's date). `reason` is one line, under 200 characters, and names the specific thing that earned or cost points — not a restatement of the title.

## Hard filters — apply first, before scoring dimensions

Any one of these sets `score` to 0 and skips the dimension breakdown (`dims` all zero, `reason` states which filter hit):

1. **Relocation required, no remote/hybrid.** Posting requires on-site with no stated remote or hybrid option, and no signal (title, description) that remote is negotiable.
2. **Below senior.** Title or leveling language indicates new grad, junior, associate, or mid-level with no senior/staff/principal/lead qualifier.
3. **Comp ceiling under $150k.** Only applies when comp is stated in the posting; postings with no stated comp are scored normally (comp dimension reflects the uncertainty, see below).

## Dimensions (0-20 each, sum to 0-100)

**Prestige** — is this a name that matters on a resume and in a network?
- 18-20: Tier 1 target (NVIDIA, Waymo, Qualcomm, Zoox, Apple, Google) or equivalent household name in the space.
- 13-17: Tier 2 target or a company with clear category leadership (Anduril, SpaceX-tier).
- 7-12: Known company, not category-defining.
- 0-6: Unknown or early-stage with no signal yet.

**Purpose** — does the work move the world? Weight toward autonomy, robotics, aerospace, AI infra, safety-critical embedded — domains adjacent to Sam's ADAS background and stated interest.
- 18-20: Directly autonomy/robotics/aerospace/AI-infra, safety-critical or frontier.
- 13-17: Adjacent domain with real technical stakes (e.g. platform infra powering the above).
- 7-12: General enterprise software, indirect impact.
- 0-6: Unclear mission or purely internal tooling.

**Remote** — how much does Sam have to give up geographically?
- 18-20: Fully remote, US-based or remote-first with occasional travel.
- 12-17: Hybrid with a reasonable cadence (1-2x/month flights plausible) or remote-eligible for senior ICs even if not advertised.
- 5-11: Hybrid requiring regular in-office presence (3+ days/week) but no relocation.
- 0-4: Effectively on-site; only survives the hard filter because remote/hybrid is technically listed as negotiable.

**Comp** — against Sam's $150k floor, $200k+ ideal.
- 18-20: Stated or well-inferred $250k+ total comp, or $200k+ base.
- 13-17: $200-250k stated, or strong inference from level + company + location.
- 7-12: $150-200k stated.
- 0-6: Comp unstated and can't be inferred with confidence (do not guess a number into `meta.comp`; leave it null and say so in `reason`).

**Trajectory** — is the team or product growing, or coasting/shrinking?
- 18-20: Explicit scaling signal (new product line, funding round, headcount growth, publicly stated roadmap milestone within 12 months).
- 13-17: Stable, established team with steady hiring.
- 7-12: No signal either way.
- 0-6: Signs of contraction (layoffs, program cancellation, hiring freeze reported elsewhere) — note the source in `reason`.

## Output

One JSONL file, one object per scored posting, written to stdout by the scoring step (the calling task captures it). Postings scoring below 60 are still included in the full table the task writes to `briefs/data/items/leads-<date>.md` (so Sam can see what was rejected and why) but are never emitted as `lead` items.
