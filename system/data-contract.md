# Orbit data contract

Everything Orbit knows lives in one append-only file: `briefs/data/events.jsonl`. One JSON object per line. The runner writes fire and task events; lanes write items, briefs, and plan drafts; the webapp writes user actions. Nobody edits past lines. The webapp folds the log into current state on load.

Lanes never write JSON by hand. They call the emitter, which adds `ts`, `fire`, and `lane` from the environment:

```bash
python3 "$ORBIT_HOME/system/emit.py" item   --kind lead --id lead-nvidia-drive-2026-09-04 \
  --title "NVIDIA, Senior Software Engineer, DRIVE platform integration" \
  --body "Remote in the US, Santa Clara flights, $215k to $290k base" \
  --meta '{"score":92,"company":"NVIDIA","url":"https://..."}'

python3 "$ORBIT_HOME/system/emit.py" update --id lead-nvidia-drive-2026-09-04 --patch '{"meta":{"score":88}}'
python3 "$ORBIT_HOME/system/emit.py" brief  --file /tmp/brief.json
python3 "$ORBIT_HOME/system/emit.py" plan   --file /tmp/plan.md
```

## Event types

| type | who writes | fields |
|------|-----------|--------|
| `fire_start` `fire_end` `fire_limit` `fire_skipped` | runner | `status`, `note`, `cost_usd` |
| `task_start` `task_end` `task_blocked` | runner | `lane`, `task`, `status`, `model`, `cost_usd`, `tokens_est`, `note` |
| `item` | lane | `lane`, `kind`, `id`, `title`, `body`, `meta` |
| `item_update` | lane | `id`, `patch` (deep-merged into the item; `meta` merges key by key) |
| `item_action` | webapp | `id`, `action` |
| `brief` | 2am fire | `date`, `accomplished[]`, `to_read[]`, `questions[]`, `tomorrow[]` |
| `plan_draft` | 10pm fire | `date`, `body` (plain text or light markdown) |
| `plan_updated` `window_synced` | webapp | bookkeeping |

## Items

An item is one thing for the user to see: a lead, a digest, an idea. Rules:

- `id` is stable and unique across time. Use `<kind>-<slug>-<yyyy-mm-dd>`. Re-emitting an existing id replaces the item; prefer `item_update` for small changes.
- `title` under 90 characters. `body` under 300. Anything longer goes in a file under `briefs/data/items/<id>.md` with `meta.path` pointing at it.
- Never mark your own items read, and never hide them. Only the user does that, through `item_action`.
- Emit only what earned its place. The primary health metric is produced vs consumed; volume you can't justify is a regression.

Kinds and the `meta` the webapp reads:

| lane | kind | meta |
|------|------|------|
| career | `lead` | `score` 0–100, `company`, `url`, `comp`, `remote` |
| career | `resume` | `status` champion \| challenger \| rejected, `version`, `graders` {a, b}, `posting` |
| career | `company` | `domain`, `url` |
| career | `idea` | `why_now`, `kill_test` |
| research | `digest` | `minutes`, `path`, `check` (question count), `check_score` "4 of 5" once taken |
| research | `problem` | `pattern`, `due` yyyy-mm-dd, `status` queued \| open \| passed \| struggled, `path` |
| research | `profile` | `side` strength \| gap, `evidence` (item id or check id) |
| operations | `inbox` | `account`, `status` connected \| not_connected, `triaged` |
| operations | `deletion` | `sender`, `count`, `account` |
| operations | `mission` | `updated` yyyy-mm-dd, `path` |

Unknown kinds still render, with title, body, and a plain kind pill. Add a kind before inventing a new lane field.

## User actions

`item_action` values: `read`, `go`, `skip`, `explore`, `prune`, `add_target`, `approve`, `check` (with `result`). `skip` and `prune` hide the item. `go`, `explore`, `add_target`, `approve` tag it. A lane reads actions on its next fire to decide what to do next, for example a lead tagged `go` gets a tailored resume run.

## Brief

The 2am fire emits exactly one `brief` per day:

```json
{"date":"2026-09-04",
 "accomplished":["Scored 14 leads, 3 above 80","Wrote the Thor digest"],
 "to_read":[{"id":"digest-thor-2026-09-04","title":"DRIVE Thor and the centralized compute stack"}],
 "questions":["Anduril is defense. Score it or skip the sector?"],
 "tomorrow":["Tailor v33 for the NVIDIA lead if you tag it go","Valid anagram returns to the ramp"]}
```

## Plan

The 10pm fire emits one `plan_draft`. The user's reply lives in `briefs/data/plan.md` (written by the webapp). The 2am fire reads `plan.md` first, acts on it, then clears it.
