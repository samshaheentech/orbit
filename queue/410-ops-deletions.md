---
lane: operations
model: haiku-4-5
effort: low
max_turns: 40
requires_mcp: gmail
tools: mcp__gmail-career__search_emails,mcp__gmail-career__read_email,mcp__gmail-career__list_email_labels,mcp__gmail-career__get_or_create_label,mcp__gmail-career__batch_modify_emails,mcp__gmail-career__modify_email,mcp__gmail-personal__search_emails,mcp__gmail-personal__read_email,mcp__gmail-personal__list_email_labels,mcp__gmail-personal__get_or_create_label,mcp__gmail-personal__batch_modify_emails,mcp__gmail-personal__modify_email,Bash(python3 lanes/operations/deletions.py *)
dir: ~/git/orbit
---
# Ops deletions — propose, and execute only what Sam approved 14+ days ago

## Rules
A deletion is a move to Trash, never a permanent delete. Only senders in an executable proposal are touched. Never send. Cap 10 new proposals per run.

## Steps
1. Run `python3 lanes/operations/deletions.py plan --emit`. It emits new `deletion` items for eligible senders (noise senders with 5+ messages, or senders the triage marked propose_delete) and returns `execute`: proposals Sam approved in the webapp at least 14 days ago, not yet executed.
2. For each entry in `execute`: in that account, `search_emails` with `from:<sender> -in:trash` (max 200), then `batch_modify_emails` with `addLabelIds: ["TRASH"]` and `removeLabelIds: ["INBOX"]` in batches of 50. Count what moved. Then `python3 lanes/operations/deletions.py executed --id <id> --count <n>`.
3. Copy this file back into `queue/410-ops-deletions.md`, then the STATUS block: proposals emitted, senders executed, messages trashed.

## If the Gmail tools are not available
Stop immediately: `STATUS: BLOCKED`, `Next: follow config/lanes/operations/SETUP.md`.
