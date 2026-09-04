# Operations lane

The lane with real side effects, so the rules come first and are not negotiable.

## Rules
1. Label and archive only. Nothing leaves the account.
2. Nothing is deleted until Sam approves a proposal in the webapp, and no approved proposal is executed until it is at least 14 days old. "Delete" means move to Trash; Gmail purges Trash on its own after 30 days, a second safety window.
3. Never send, reply, forward, draft, or create drafts. The OAuth token has no send or compose scope (`SETUP.md`), so the tools do not exist for the model either.
4. Never touch settings, filters, forwarding, or delegation.
5. Anything that looks personal, legal, financial, medical, or career-related stays in the inbox untouched. When unsure, keep.
6. Cap 200 messages per run per account; cap 10 new deletion proposals per run.

## Accounts
| server name | account | purpose |
|-------------|---------|---------|
| `gmail-career` | SamShaheen.tech@gmail.com | career, clean, keep it that way |
| `gmail-personal` | personal Gmail | high noise, triage and clean |

Tool names inside a fire are `mcp__<server name>__<tool>`, e.g. `mcp__gmail-personal__search_emails`.

## Taxonomy
Labels, created on first use with `get_or_create_label`:
- `orbit/receipts` (orders, invoices, confirmations)
- `orbit/newsletters` (anything with a List-Unsubscribe header or newsletter wording)
- `orbit/career` (recruiters, ATS mail, interview scheduling, job alerts)
- `orbit/personal` (humans writing to Sam)
- `orbit/noise` (promotions, bulk, dead subscriptions, notifications nobody reads)

Archive means remove `INBOX`. Only `orbit/newsletters` and `orbit/noise` get archived automatically. `orbit/receipts` gets labeled and archived after 3 days. Career and personal never get archived by the agent.

## Sender table
`config/lanes/operations/senders.json` is the learned memory: one entry per sender per account with `label`, `action` (`keep` | `archive` | `propose_delete`), counts, and dates. `lanes/operations/triage_rules.py` applies it deterministically; the model only decides for senders the table has never seen, and its decision is written back so the next run needs no model call for that sender.

## Tasks
| task | model | when | what |
|------|-------|------|------|
| `400-ops-triage` | haiku-4-5 | daily | label and archive both accounts |
| `410-ops-deletions` | haiku-4-5 | daily | propose deletions per sender; execute approved ones past 14 days |
| `420-ops-mission` | sonnet-5 | daily | keep `config/lanes/career/mission.md` current |

`400` and `410` carry `requires_mcp: gmail`; until both servers are configured, `run.sh` leaves them in the queue and logs a blocked event so the morning brief keeps pointing at `SETUP.md`.

## Recurrence
Each task copies its own file back into `queue/` as its last step before the STATUS block.
