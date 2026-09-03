#!/usr/bin/env python3
"""
orbit/server.py — local webapp server
Serves orbit/briefs/ on http://localhost:4242
Handles POST /api/event for webapp → disk writes (tag lead, prune idea, mark read, plan input)
Kept intentionally minimal: stdlib only, no dependencies.
"""

import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

PORT = int(os.environ.get("ORBIT_PORT", 4242))
BRIEFS_DIR = Path(os.environ.get("ORBIT_BRIEFS", Path(__file__).resolve().parent / "briefs"))
EVENTS_FILE = BRIEFS_DIR / "data" / "events.jsonl"
PLAN_FILE = BRIEFS_DIR / "data" / "plan.md"


def append_event(event: dict):
    event["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    event["source"] = "webapp"
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def read_events(limit: int = 500) -> list:
    if not EVENTS_FILE.exists():
        return []
    lines = EVENTS_FILE.read_text().strip().split("\n")
    lines = [l for l in lines if l.strip()]
    parsed = []
    for l in lines[-limit:]:
        try:
            parsed.append(json.loads(l))
        except Exception:
            pass
    return parsed


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access log

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        content = path.read_bytes()
        ext = path.suffix.lower()
        mime = {
            ".html": "text/html",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".jsonl": "application/x-ndjson",
            ".md": "text/markdown",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API routes
        if path == "/api/events":
            self.send_json(read_events())
            return

        if path == "/api/plan":
            content = PLAN_FILE.read_text() if PLAN_FILE.exists() else ""
            self.send_json({"content": content})
            return

        if path == "/api/health":
            self.send_json({"status": "ok", "ts": datetime.now(timezone.utc).isoformat()})
            return

        # Static files
        if path == "/" or path == "":
            file_path = BRIEFS_DIR / "index.html"
        else:
            # Safety: don't serve outside briefs dir
            rel = path.lstrip("/")
            file_path = (BRIEFS_DIR / rel).resolve()
            if not str(file_path).startswith(str(BRIEFS_DIR.resolve())):
                self.send_response(403)
                self.end_headers()
                return

        self.send_file(file_path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body) if body else {}
        except Exception:
            self.send_json({"error": "invalid json"}, 400)
            return

        if path == "/api/event":
            # Webapp writes: tag_lead, prune_idea, mark_read, plan_update, quality_rating
            event_type = data.get("type", "webapp_action")
            append_event(data)
            self.send_json({"ok": True})
            return

        if path == "/api/plan":
            # Save plan input
            content = data.get("content", "")
            PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            PLAN_FILE.write_text(content)
            append_event({"type": "plan_updated", "chars": len(content)})
            self.send_json({"ok": True})
            return

        self.send_json({"error": "not found"}, 404)


def main():
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    (BRIEFS_DIR / "data").mkdir(parents=True, exist_ok=True)

    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Orbit server running at http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")


if __name__ == "__main__":
    main()
