#!/usr/bin/env python3
"""ROVA Film Crew — Clarity Handoff HTTP Server.

Lightweight server that Clarity (or any ROVA agent) can POST job specs to.
Receives JSON, validates, writes to jobs/inbox/, optionally auto-starts pipeline.

Usage:
    python scripts/server.py --port 5040
    python scripts/server.py --port 5040 --auto-run
"""
import argparse
import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread


def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InboxServer(BaseHTTPRequestHandler):
    inbox_dir = os.path.join(get_project_root(), "jobs", "inbox")

    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args}")

    def do_POST(self):
        if self.path == "/jobs":
            self._handle_post_job()
        else:
            self._send_json(404, {"error": f"unknown path: {self.path}"})

    def _handle_post_job(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json(400, {"error": "empty body"})
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_json(400, {"error": f"invalid JSON: {e}"})
            return

        job_id = data.get("job_id")
        if not job_id:
            self._send_json(400, {"error": "missing job_id"})
            return

        # Write to inbox
        os.makedirs(self.inbox_dir, exist_ok=True)
        path = os.path.join(self.inbox_dir, f"{job_id}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[server] Received job {job_id}: {data.get('title')}")
        resp = {"status": "accepted", "job_id": job_id, "path": path}

        # Auto-run if requested
        if getattr(self.server, "auto_run", False):
            try:
                import subprocess
                root = get_project_root()
                result = subprocess.run(
                    [sys.executable, "main.py", "--job", path, "--script-mode"],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                resp["pipeline_status"] = "started" if result.returncode == 0 else "failed"
                resp["pipeline_log"] = result.stdout[-500:] if result.stdout else ""
            except Exception as e:
                resp["pipeline_status"] = "error"
                resp["pipeline_error"] = str(e)

        self._send_json(202, resp)

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        self._send_json(200, {
            "service": "ROVA Film Crew Handoff Server",
            "version": "0.2",
            "endpoints": {
                "POST /jobs": "Submit a job spec JSON",
            },
            "inbox": self.inbox_dir,
        })


def run_server(port, auto_run=False):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, InboxServer)
    httpd.auto_run = auto_run

    def serve():
        print(f"[server] Starting on http://0.0.0.0:{port}/jobs")
        print(f"[server] Inbox: {InboxServer.inbox_dir}")
        print(f"[server] Auto-run: {'on' if auto_run else 'off'}")
        httpd.serve_forever()

    t = Thread(target=serve, daemon=True)
    t.start()
    print("[server] Running. Press Ctrl+C to stop.\n")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[server] Stopping...")
        httpd.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5040)
    parser.add_argument("--auto-run", action="store_true", help="Auto-run pipeline on each received job")
    args = parser.parse_args()
    run_server(args.port, args.auto_run)


if __name__ == "__main__":
    main()
