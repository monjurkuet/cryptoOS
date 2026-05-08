#!/usr/bin/env python3
"""Independent lightweight health proxy for market-scraper.

Serves on 127.0.0.1:3847 and proxies health checks to market-scraper on 3845.
"""
from __future__ import annotations

import json
import socket
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "http://127.0.0.1:3845/health/live"
HOST = "127.0.0.1"
PORT = 3847
TIMEOUT = 3


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _probe(self) -> tuple[int, dict]:
        try:
            req = urllib.request.Request(UPSTREAM, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace").strip()
            # Preserve expected strict success payload when upstream is healthy.
            if raw == '{"status":"alive"}':
                return 200, {"status": "alive"}
            # Accept equivalent JSON payloads that include alive status.
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("status") == "alive" and "warning" not in parsed:
                return 200, {"status": "alive"}
            return 503, {"status": "degraded", "detail": raw[:300]}
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            return 503, {"status": "down", "error": str(exc)[:300]}

    def do_GET(self) -> None:
        if self.path in ("/", "/health", "/health/live"):
            code, payload = self._probe()
            self._send_json(code, payload)
            return
        self._send_json(404, {"error": "not_found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()
