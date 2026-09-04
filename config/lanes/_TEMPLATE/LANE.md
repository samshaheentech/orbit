# <Lane name>

## Goal
One paragraph: what this lane produces for the user and why it earns its place in the brief.

## Sources of truth
Which files and which parts of the log this lane reads before it acts (`config/user.md`, its own state under `state/<lane>/`, items and actions in the log).

## Tasks and cadence
| task | model | when | what |
|------|-------|------|------|
| `NNN-<lane>-<name>` | sonnet-5 | daily | one line |

## Item kinds
Which kinds from `system/data-contract.md` this lane emits, and what goes in `meta`. Add a kind to the contract before inventing one.

## Rules
Hard limits: caps per run, what never happens, what needs the user's approval.

## Recurrence
Each task copies its own file back into `queue/` as its last step before the STATUS block. Use `days:` and `hours:` frontmatter for cadence instead of checking the date in the prompt.
