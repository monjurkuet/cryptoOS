#!/usr/bin/env python3
"""Standalone health proxy for market-scraper.

Runs independently of the main market-scraper process.
Checks if the main process is alive and responsive,
and provides a health endpoint on port 3847.

This is needed because the main process can get stuck
in swap thrashing on the budget VPS (961MB RAM),
making even its thread-based health server unresponsive
due to GIL contention.
"""
import http.server
import json
import socket
import subprocess
import signal
import sys

PORT = 3847
MAIN_PORT = 3846  # Thread health server port
SERVICE_NAME = "market-scraper"


def check_process_alive():
    """Check if the market-scraper systemd service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def check_port_responding():
    """Try to connect to the main health server."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("127.0.0.1", MAIN_PORT))
        sock.sendall(b"GET /health/live HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        data = sock.recv(1024)
        sock.close()
        return b"alive" in data
    except Exception:
        return False


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health/live":
            # Quick check: is the process running?
            process_alive = check_process_alive()
            port_responding = check_port_responding()

            if port_responding:
                body = json.dumps({"status": "alive"}).encode()
                self.send_response(200)
            elif process_alive:
                # Process is running but not responding (stuck in swap)
                body = json.dumps({
                    "status": "alive",
                    "warning": "main_process_unresponsive",
                    "detail": "Process is active but health endpoint not responding"
                }).encode()
                self.send_response(200)  # Still alive, just degraded
            else:
                body = json.dumps({"status": "dead"}).encode()
                self.send_response(503)

            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except BrokenPipeError:
                pass
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs


class ThreadedHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    server = ThreadedHTTPServer(("127.0.0.1", PORT), HealthHandler)
    print(f"Health proxy listening on port {PORT}", flush=True)

    def signal_handler(sig, frame):
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    server.serve_forever()


if __name__ == "__main__":
    main()
