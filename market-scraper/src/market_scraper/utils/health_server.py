"""Thread-based liveness health server.

Runs a minimal HTTP server on a dedicated thread, completely independent
of the asyncio event loop. This ensures the /health/live endpoint always
responds even when the main event loop is blocked by MongoDB writes,
WebSocket processing, or other heavy async operations.

The server only handles GET /health/live and returns {"status":"alive"}.
All other requests get 404.

Uses ThreadingHTTPServer so each request runs in its own thread,
preventing GIL contention with the main asyncio event loop.

Usage in lifespan:
    from market_scraper.utils.health_server import ThreadHealthServer
    health_server = ThreadHealthServer(port=3846)
    health_server.start()
    # ... later ...
    health_server.stop()
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a new thread."""
    daemon_threads = True
    allow_reuse_address = True


class _LivenessHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that only serves /health/live."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health/live":
            body = json.dumps({"status": "alive"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except BrokenPipeError:
                pass  # Client disconnected, ignore
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        # Suppress default stderr logging to avoid noise
        pass


class ThreadHealthServer:
    """Liveness HTTP server running on a dedicated daemon thread.

    This server is immune to asyncio event loop blocking because it
    uses the stdlib blocking HTTP server on its own thread with its
    own socket. No dependency on asyncio, FastAPI, or the main loop.
    Each request is handled in its own thread via ThreadingMixIn,
    ensuring the response is sent even when the main thread holds the GIL.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 3846) -> None:
        self._host = host
        self._port = port
        self._server: _ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the health server on a daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._server = _ThreadingHTTPServer((self._host, self._port), _LivenessHandler)

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="health-liveness-server",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the health server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
