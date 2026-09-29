#!/usr/bin/env python3
"""Serve only the generated dashboard on loopback for Tailscale Serve."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard.html"
PORT = 48191


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.respond(False)

    def do_GET(self):
        self.respond(True)

    def respond(self, body):
        if self.path.split("?", 1)[0] not in ("/", "/health", "/health/"):
            self.send_error(404)
            return
        try:
            size = DASHBOARD.stat().st_size
            if body:
                stream = DASHBOARD.open("rb")
        except OSError:
            self.send_error(503, "Dashboard not built")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if body:
            with stream:
                while chunk := stream.read(65536):
                    self.wfile.write(chunk)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
