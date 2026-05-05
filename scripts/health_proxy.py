#!/usr/bin/env python3
"""Standalone health proxy for market-scraper.

Runs independently of the main market-scraper process.
Checks if the main process is alive and responsive,
and provides a health endpoint on port 3847.

This is needed because the main process can get stuck
in swap thrashing on the budget VPS (961MB RAM),
making even its thread-based health server unresponsive
due to GIL contention.

Health check strategy (primary → fallback):
1. Check the main API (port 3845) /health/live — this is the real
   indicator of service health since it serves all API endpoints.
2. Check the thread health server (port 3846) /health/live — backup
   check; this thread-based server was meant to be GIL-independent
   but can still stall under heavy swap thrashing.
3. Check systemd service status — last resort, only tells us the
   process exists, not that it's functional.
"""
import http.server
import json
import socket
import subprocess
import signal
import sys

PORT = 3847
MAIN_API_PORT = 3845  # Main FastAPI/uvicorn server
THREAD_HEALTH_PORT = 3846  # Thread-based liveness server
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


def check_port_http(port, path="/health/live", expected=b"alive"):
    """Try an HTTP GET on a local port and check if expected string is in response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("127.0.0.1", port))
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode())
        # Read full response - headers may arrive before body in separate recv calls
        data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        sock.close()
        return expected in data
    except Exception:
        return False


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health/live":
            # Primary: check the main API server (port 3845) — the real service
            main_api_responding = check_port_http(MAIN_API_PORT)

            # Fallback: check the thread health server (port 3846)
            thread_health_responding = check_port_http(THREAD_HEALTH_PORT)

            # Last resort: check systemd service status
            process_alive = check_process_alive()

            if main_api_responding:
                # Main API is healthy — the service is fully functional
                body = json.dumps({"status": "alive"}).encode()
                self.send_response(200)
            elif thread_health_responding:
                # Thread server responds but main API doesn't — degraded
                body = json.dumps({
                    "status": "alive",
                    "warning": "main_api_unresponsive",
                    "detail": "Thread health server responding but main API is not"
                }).encode()
                self.send_response(200)
            elif process_alive:
                # Process is running but neither health endpoint responds (stuck in swap)
                body = json.dumps({
                    "status": "alive",
                    "warning": "main_process_unresponsive",
                    "detail": "Process is active but no health endpoints are responding"
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
        pass # Suppress logs


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
