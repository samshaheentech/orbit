# Sim

Where interviews get rehearsed. Astronauts don't prep, they get in the sim.

## Goal
By the time Sam sits in a loop, every question they're likely to ask has been asked already, his stories are in tight STAR form he can say in 90 seconds, and his answers have been graded by something that read the posting.

## Sources of truth
Leads tagged `go` (their postings and scored notes), the story bank (`config/lanes/sim/stories.json`, seeded from the mission file's interview ammo), `config/user.md`, and Sam's own answers and grades in the log.

## Tasks and cadence
| task | model | when | what |
|------|-------|------|------|
| `500-sim-drills` | sonnet-5 | daily | a question set per newly tagged lead; one general drill when there's nothing new |
| `510-sim-stories` | sonnet-5 | daily | one STAR draft from the bank, long form plus the 90-second spoken version |
| `520-sim-grade` | fable-5-1 | daily, heavy | grades every answer Sam submitted since the last run |

## Item kinds
- `drill`: one question. `meta.lead` (lead id or `general`), `meta.category` behavioral | systems | domain | curveball, `meta.question`, `meta.path` (the set file). After Sam answers: `meta.answered` date. After grading: `meta.score` 1 to 5.
- `story`: one STAR draft. `meta.slug`, `meta.path`. Approve keeps it in the bank as canon; skip sends it back with a note in `plan.md`.
- `feedback`: the grade. `meta.drill`, `meta.score`, `meta.landed`, `meta.missing`, `meta.cut`, `meta.path`.

User action `answer` (with `text`) is how Sam submits. The webapp records it; `520` consumes it.

## Question sets
Eight per lead: three behavioral (from the posting's competencies and the story bank), two systems (scoped to what the team builds), two domain (centralized compute, safety, the stack named in the posting), one curveball (the question they'll ask that he'd rather they didn't). Written to `briefs/data/items/drillset-<lead>-<date>.md`; each question also emitted as its own `drill` item so the sim can serve them one at a time.

## Grading rubric (Fable)
Against the posting and the story bank: did the answer land the point the question was fishing for; what was missing that the bank had; what to cut to fit 90 seconds; one line Sam can say instead. Score 1 to 5. A 4 or 5 closes the drill; under 4 re-queues it a week later with the feedback attached.

## Cost caps
Drills: one Sonnet run, at most 16 questions per night. Stories: one draft per night. Grade: one Fable run over all pending answers, skipped when there are none.

## Recurrence
Each task copies its own file back into `queue/` before its STATUS block.
