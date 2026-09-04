# Research & learning lane

## Goal
Make Sam a weapon of knowledge at the intersection of his strengths, his gaps, and where the world is going. Evidence only: nothing is asserted about him without a check score, a passed or struggled problem, or a digest he actually read.

## Sources of truth
`config/user.md`, the knowledge profile (`profile` items in the log), leads and companies Sam tagged `go` or `add_target`, and `state/research/topics.json` (seeded from `config/lanes/research/topics.seed.json` on first run).

## Tasks and cadence
| task | model | when | what |
|------|-------|------|------|
| `300-research-digest` | sonnet-5 | daily | one digest, 15 to 25 minutes of reading, with a 5-question check |
| `310-research-ramp` | sonnet-5 | daily | the coding ramp: check open problems, keep two open |
| `320-research-profile` | fable-5-1 | Sundays | the knowledge profile from evidence; reprioritizes topics |

## Digest format
File: `briefs/data/items/digest-<slug>-<date>.md`. Body first, then exactly this check block, which the webapp parses:

```
## Check
1. Question text?
   a) option
   b) option
   c) option
   d) option
2. ...
<!-- answers: 1b 2a 3d 4c 5a -->
```

Five questions, four options each, one correct. The answers comment must be the last line. Emit the item with `meta.minutes`, `meta.path`, `meta.check: 5`. Prefer topics touching a lead Sam tagged `go` this week. Never repeat a topic whose check was taken unless the profile recorded a gap there.

## Coding ramp
Roadmap: hash maps, two pointers, sliding window, binary search, stacks, linked lists, trees and BFS/DFS, heaps, DP taste. Keep two problems open. Each problem lives in `ramp/<slug>/`:
- `README.md` statement, constraints, examples, the pattern
- `solution.py` with the function signature and `pass`, nothing more
- `test_<slug>.py` plain asserts, runnable with `python3 test_<slug>.py`
- `meta.json` `{id, slug, pattern, status, due, return, signature, hints}` maintained by `lanes/research/ramp_check.py`

Rules: Sam writes all code. No solutions in `solution.py`, ever. A problem untouched or failing past its due date becomes `struggled`, gets one hint appended to its README, and is rescheduled two days out. A passed problem returns seven days later for retention (`meta.return`); the checker resets `solution.py` to the signature and keeps the old one as `solution.passed.py`.

## Knowledge profile
`profile` items, `meta.side` strength or gap, `meta.evidence` an item id or check id. A closed gap gets `item_update` with `meta.closed`. Never delete a line; the history is the point.

## Cost caps
Digest: one Sonnet run, under 2,500 words. Ramp: no model call when nothing changed. Profile: one Fable run a week.

## Recurrence
Each task copies its own file back into `queue/` as its last step before the STATUS block (see the career lane's Recurrence note). `320` also carries `days: sun` so `run.sh` leaves it in the queue on other days.
