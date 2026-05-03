# src/market_scraper/utils/watchdog.py

"""Systemd watchdog heartbeat utility.

Sends WATCHDOG=1 notifications to systemd via the NOTIFY_SOCKET
to prevent WatchdogSec from killing the process.

Uses a **threaded** heartbeat (not asyncio) so that watchdog pings
continue even when the event loop is blocked by slow I/O operations
(e.g. remote MongoDB Atlas writes that take 10-120s).

Uses raw socket communication (no systemd-daemon dependency needed).
"""

import os
import socket
import threading
import structlog

logger = structlog.get_logger(__name__)


def _send_raw_notify(message: str) -> None:
    """Send a raw notification to systemd via NOTIFY_SOCKET.

    Args:
        message: The notification string (e.g. "WATCHDOG=1")
    """
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        # No notify socket — not running under systemd watchdog, skip silently
        return

    try:
        # NOTIFY_SOCKET can be either a Unix socket path or an abstract socket
        # (prefixed with @). Abstract sockets live in the namespace and don't
        # exist on the filesystem.
        if notify_socket.startswith("@"):
            # Abstract socket: replace leading @ with null byte
            addr = "\0" + notify_socket[1:]
        else:
            addr = notify_socket

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.connect(addr)
            sock.sendall(message.encode("utf-8"))
        finally:
            sock.close()
    except Exception as e:
        logger.warning("watchdog_notify_failed", error=str(e))


def notify_ready() -> None:
    """Notify systemd that the service is ready (READY=1)."""
    _send_raw_notify("READY=1")


def notify_watchdog() -> None:
    """Notify systemd that the service is still alive (WATCHDOG=1)."""
    _send_raw_notify("WATCHDOG=1")


class WatchdogHeartbeat:
    """Threaded watchdog heartbeat that periodically sends WATCHDOG=1 to systemd.

    Runs in a **daemon thread** instead of an asyncio task so that watchdog
    pings continue even when the event loop is blocked. This is critical for
    services with slow synchronous operations (e.g. remote MongoDB writes)
    that can freeze the event loop for 10-120+ seconds.

    The heartbeat interval is automatically calculated from the
    WATCHDOG_USEC environment variable (set by systemd when WatchdogSec
    is configured). We use half the interval as recommended by systemd docs.

    Usage:
        heartbeat = WatchdogHeartbeat()
        await heartbeat.start()  # starts background thread
        # ... service runs ...
        await heartbeat.stop()  # stops background thread
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event = threading.Event()
        self._interval: float = self._calculate_interval()

    def _calculate_interval(self) -> float:
        """Calculate heartbeat interval from WATCHDOG_USEC env var.

        Systemd sets WATCHDOG_USEC when WatchdogSec is configured.
        We use half the timeout as the heartbeat interval (recommended).
        Falls back to 120s if not set (i.e. not under systemd watchdog).
        """
        watchdog_usec = os.environ.get("WATCHDOG_USEC")
        if watchdog_usec:
            try:
                timeout_sec = int(watchdog_usec) / 1_000_000
                interval = timeout_sec / 2
                logger.info(
                    "watchdog_configured",
                    timeout_sec=timeout_sec,
                    heartbeat_interval=interval,
                    mode="threaded",
                )
                return interval
            except (ValueError, ZeroDivisionError):
                pass
        # Not running under systemd watchdog — use a long default
        return 120.0

    async def start(self) -> None:
        """Start the watchdog heartbeat background thread.

        Uses a daemon thread so the heartbeat runs independently of the
        asyncio event loop. This ensures watchdog pings are sent even
        when the event loop is blocked by slow I/O.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        logger.info("watchdog_heartbeat_starting", interval=self._interval, mode="threaded")

        def _heartbeat_loop():
            while not self._stop_event.wait(timeout=self._interval):
                try:
                    notify_watchdog()
                    logger.debug("watchdog_heartbeat_sent")
                except Exception as e:
                    logger.warning("watchdog_heartbeat_error", error=str(e))

        self._thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="watchdog-hb")
        self._thread.start()

    async def stop(self) -> None:
        """Stop the watchdog heartbeat background thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("watchdog_heartbeat_stopped")
