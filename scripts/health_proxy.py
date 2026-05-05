#!/usr/bin/env python3
"""Standalone health proxy for market-scraper.

Runs independently of the main market-scraper process.
Checks if the main process is alive and responsive,
and provides a health endpoint on port 3847.

This is needed because the main process can get stuck
in swap thrashing on the budget VPS (961MB RAM),
making even its thread-based health server unresponsive
due to GIL contention.

Health check strategy:
- Check both the main API (port 3845) and thread health server (port 3846)
  concurrently with a 3s timeout each. Either one responding proves the
  process is alive and functional. Under heavy swap thrashing on a 1-core
  VPS, these servers alternate responsiveness depending on CPU scheduling,
  so checking both concurrently maximizes the chance of a quick response.
- If neither port responds, fall back to systemd service status check.
"""
import concurrent.futures
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
CHECK_TIMEOUT = 3  # seconds per port check


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
        sock.settimeout(CHECK_TIMEOUT)
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


def check_any_port_responding():
    """Check both health ports concurrently. Returns True if either responds."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(check_port_http, MAIN_API_PORT): "main_api",
            executor.submit(check_port_http, THREAD_HEALTH_PORT): "thread_health",
        }
        # Wait up to CHECK_TIMEOUT for any result — as soon as one succeeds, return True
        done, not_done = concurrent.futures.wait(
            futures, timeout=CHECK_TIMEOUT,
            return_when=concurrent.futures.FIRST_COMPLETED,
        )
        # Check completed futures
        for future in done:
            try:
                if future.result():
                    return True
            except Exception:
                pass
        # Check remaining (may have completed by now)
        for future in not_done:
            try:
                if future.result(timeout=0.5):
                    return True
            except Exception:
                pass
        return False


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health/live":
            if check_any_port_responding():
                # At least one health endpoint is responding — service is alive
                body = json.dumps({"status": "alive"}).encode()
                self.send_response(200)
            elif check_process_alive():
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
