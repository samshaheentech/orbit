---
lane: operations
model: haiku-4-5
effort: low
max_turns: 50
requires_mcp: gmail-career
tools: mcp__gmail-career__search_emails,mcp__gmail-career__read_email,mcp__gmail-career__list_email_labels,mcp__gmail-career__get_or_create_label,mcp__gmail-career__batch_modify_emails,mcp__gmail-career__modify_email,mcp__gmail-personal__search_emails,mcp__gmail-personal__read_email,mcp__gmail-personal__list_email_labels,mcp__gmail-personal__get_or_create_label,mcp__gmail-personal__batch_modify_emails,mcp__gmail-personal__modify_email,Bash(python3 lanes/operations/triage_rules.py *)
dir: ~/git/orbit
---
# Ops triage — label and archive, active accounts

## Rules (from config/lanes/operations/LANE.md, not negotiable)
Label and archive only. Never send, reply, forward, or draft. Never delete. Never touch settings or filters. Personal, legal, financial, medical, and career mail stays in the inbox untouched. When unsure, keep. Cap 200 messages per account.

## Steps
0. Read `config/lanes/operations/accounts.json`. Only act on accounts where `active` is true (today: just career). For each inactive account, do nothing and note it as skipped, not blocked, in the STATUS block — it is not an error, personal just is not connected yet.
1. For each active account, in order: `search_emails` with `in:inbox newer_than:2d` (first run: `in:inbox newer_than:30d`), max 200. Build a JSON list `[{"id","from","subject","snippet","list_unsubscribe":<true if the message has a List-Unsubscribe header or an unsubscribe link in the snippet>,"labels":[...]}]` and write it to `state/operations/<account>-inbox.json` (create the folder).
2. Run `python3 lanes/operations/triage_rules.py decide --account <career|personal> --messages state/operations/<account>-inbox.json`. It applies the sender table and the taxonomy and returns `apply`, `unknown`, `kept`.
3. For each entry in `unknown`: decide the label from the samples using the taxonomy in `config/lanes/operations/taxonomy.json`. Bulk or promotional means `orbit/noise` + `archive`; a real newsletter means `orbit/newsletters` + `archive`; a human, a company Sam deals with, anything protected, or anything you are not sure about means `orbit/personal` (or `orbit/career`) + `keep`. Record each with `python3 lanes/operations/triage_rules.py learn --account <account> --sender <sender> --label <label> --action <keep|archive> --note "<reason>"`. Then re-run step 2 so the new rules apply.
4. Ensure labels exist with `get_or_create_label`, then apply the `apply` list with `batch_modify_emails` in batches of 50: `addLabelIds` the label id, and `removeLabelIds: ["INBOX"]` only where `archive` is true.
5. Emit one inbox item per account, replacing yesterday's: `python3 $ORBIT_HOME/system/emit.py item --kind inbox --id inbox-<account>-status --title "<address>" --body "<n> triaged, <a> archived, <u> new senders learned" --meta '{"account": "<account>", "status": "connected", "triaged": <n>}'`
6. Copy this file back into `queue/400-ops-triage.md`, then the STATUS block with the counts per account.

## If gmail-career itself is not available
Stop immediately: `STATUS: BLOCKED`, `Next: follow config/lanes/operations/SETUP.md`.

## Adding personal later
When Sam runs the personal auth and registers `gmail-personal`, he flips `active` to `true` for `personal` in `accounts.json` (or asks Orbit to); nothing else about this task changes.
