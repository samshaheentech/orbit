#!/usr/bin/env python3
"""
Deterministic triage. The model never decides what the sender table already knows.

  triage_rules.py decide --account personal --messages msgs.json       -> decisions JSON on stdout
  triage_rules.py learn  --account personal --sender x@y --label orbit/noise --action archive [--note "..."]
  triage_rules.py --fixtures                                             -> runs decide on lanes/operations/fixtures/messages.json

messages.json: [{"id","from","subject","snippet","list_unsubscribe":bool,"labels":[...]}]
decisions:     {"apply":[{"id","sender","label","archive":bool}], "unknown":[{"sender","samples":[subjects]}], "kept":[ids]}
"""
import argparse, datetime as dt, json, os, re, sys
from pathlib import Path

HOME = Path(os.environ.get("ORBIT_HOME", Path(__file__).resolve().parents[2]))
CFG = HOME / "config" / "lanes" / "operations"
SENDERS = CFG / "senders.json"
TAX = CFG / "taxonomy.json"
PROTECT = ["legal", "court", "irs", "tax", "bank", "medical", "doctor", "insurance", "lease", "contract", "visa", "passport"]


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def sender_of(frm):
    m = re.search(r"<([^>]+)>", frm or "")
    return (m.group(1) if m else (frm or "")).strip().lower()


def rule_label(msg, tax):
    subj = (msg.get("subject") or "").lower(); frm = sender_of(msg.get("from")); dom = frm.split("@")[-1]
    if any(w in subj for w in PROTECT):
        return "protected"
    for label in ("orbit/career", "orbit/receipts", "orbit/noise", "orbit/newsletters"):
        t = tax.get(label, {})
        if any(dom.endswith(d) for d in t.get("domains", [])): return label
        if any(w in subj for w in t.get("subject", [])): return label
        if t.get("list_unsubscribe") and msg.get("list_unsubscribe"): return label
        if any(w in frm.split("@")[0] for w in t.get("from_words", [])): return label
    return None


def decide(account, messages, senders, tax, today):
    table = {(s["sender"], s["account"]): s for s in senders["senders"]}
    apply, unknown, kept = [], {}, []
    for m in messages:
        frm = sender_of(m.get("from"))
        if not frm:
            kept.append(m["id"]); continue
        s = table.get((frm, account))
        if s:
            s["count"] = int(s.get("count", 0)) + 1; s["last_seen"] = today
            if s["action"] == "keep":
                kept.append(m["id"])
            else:
                apply.append({"id": m["id"], "sender": frm, "label": s["label"], "archive": s["action"] in ("archive", "propose_delete")})
            continue
        label = rule_label(m, tax)
        if label == "protected":
            kept.append(m["id"]); continue
        if label in ("orbit/newsletters", "orbit/noise"):
            apply.append({"id": m["id"], "sender": frm, "label": label, "archive": True})
            table[(frm, account)] = {"sender": frm, "account": account, "label": label, "action": "archive", "count": 1, "first_seen": today, "last_seen": today, "note": "rule"}
        elif label in ("orbit/career", "orbit/receipts"):
            apply.append({"id": m["id"], "sender": frm, "label": label, "archive": False})
            table[(frm, account)] = {"sender": frm, "account": account, "label": label, "action": "keep", "count": 1, "first_seen": today, "last_seen": today, "note": "rule"}
        else:
            kept.append(m["id"])
            unknown.setdefault(frm, []).append((m.get("subject") or "")[:80])
    senders["senders"] = list(table.values())
    return {"apply": apply, "unknown": [{"sender": k, "samples": v[:3]} for k, v in unknown.items()], "kept": kept}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("decide"); d.add_argument("--account", required=True); d.add_argument("--messages", required=True); d.add_argument("--now")
    l = sub.add_parser("learn"); l.add_argument("--account", required=True); l.add_argument("--sender", required=True); l.add_argument("--now")
    l.add_argument("--label", required=True); l.add_argument("--action", required=True, choices=["keep", "archive", "propose_delete"]); l.add_argument("--note", default="model")
    ap.add_argument("--fixtures", action="store_true"); ap.add_argument("--now")
    a = ap.parse_args()
    today = (dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now()).date().isoformat()
    senders, tax = load(SENDERS, {"senders": []}), load(TAX, {})
    if a.fixtures:
        msgs = json.loads((HOME / "lanes" / "operations" / "fixtures" / "messages.json").read_text(encoding="utf-8"))
        print(json.dumps(decide("personal", msgs, senders, tax, today), indent=1)); return
    if a.cmd == "decide":
        msgs = json.loads(Path(a.messages).read_text(encoding="utf-8"))
        out = decide(a.account, msgs, senders, tax, today)
        SENDERS.write_text(json.dumps(senders, indent=1), encoding="utf-8")
        print(json.dumps(out, indent=1))
    elif a.cmd == "learn":
        table = {(s["sender"], s["account"]): s for s in senders["senders"]}
        k = (a.sender.lower(), a.account)
        row = table.get(k, {"sender": a.sender.lower(), "account": a.account, "count": 0, "first_seen": today})
        row.update({"label": a.label, "action": a.action, "last_seen": today, "note": a.note}); table[k] = row
        senders["senders"] = list(table.values())
        SENDERS.write_text(json.dumps(senders, indent=1), encoding="utf-8")
        print(json.dumps({"ok": True, "sender": a.sender.lower(), "action": a.action}))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
