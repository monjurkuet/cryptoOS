# src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py

"""Trader WebSocket Collector.

Collects real-time position and order data for tracked traders.
Uses webData2 subscription type for comprehensive trader data.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog

from market_scraper.config.market_config import BufferConfig
from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)

class _RateLimiter:
    """Simple sliding-window rate limiter (token-bucket style).

    Caps outgoing HTTP requests to a configurable max-per-second rate.
    Thread-safe for single-event-loop usage (no true cross-thread concern).
    """

    def __init__(self, max_rate: float = 10.0, window: float = 1.0) -> None:
        self._max_rate = max_rate
        self._window = window
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available under the rate limit."""
        while True:
            async with self._lock:
                now = time.monotonic()
                # Evict timestamps outside the sliding window
                cutoff = now - self._window
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max_rate:
                    self._timestamps.append(now)
                    return
                # Compute how long to wait for the oldest timestamp to expire
                wait = self._timestamps[0] - cutoff
            await asyncio.sleep(wait)


class TraderWebSocketCollector:
    """Collects real-time trader data via WebSocket.

    Features:
    - Multiple concurrent connections (configurable, default 5)
    - Event-driven position saves (only when changed)
    - BTC-only filtering (configurable)
    - Auto-reconnect with exponential backoff
    - Batch processing with message buffer
    - TTL-based cleanup to prevent unbounded memory growth

    Storage Optimization: 85% reduction through event-driven saves
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    # TTL for position state (1 hour)
    POSITION_STATE_TTL = 3600
    # Max tracked positions (reduced from 200 to 150 for VPS memory pressure)
    MAX_TRACKED_POSITIONS = 150

    # Global rate limiter: caps HTTP POST requests to ~10/s for the Hyperliquid API
    _api_rate_limiter = _RateLimiter(max_rate=10.0, window=1.0)

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
        on_trader_data: Callable[[dict[str, Any]], None] | None = None,
        on_bootstrap_event: Callable[[StandardEvent], Any] | None = None,
        buffer_config: BufferConfig | None = None,
    ) -> None:
        """Initialize the trader WebSocket collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
            on_trader_data: Optional callback for trader data
            on_bootstrap_event: Optional callback to handle bootstrap events
            directly (e.g., deterministic repository upserts)
            buffer_config: Buffer and flush configuration
        """
        self.event_bus = event_bus
        self.config = config
        self._on_trader_data = on_trader_data
        self._on_bootstrap_event = on_bootstrap_event

        # Connection management
        self._clients: list[TraderWSClient] = []
        self._num_clients = 20  # Hyperliquid limits 10 user subscriptions per WS connection
        self._batch_size = 10  # Must match Hyperliquid's per-connection user limit

        # State
        self._running = False
        self._tracked_traders: list[str] = []

        # Event-driven optimization: Track last saved state per trader with TTL
        # address -> {hash, timestamp}
        self._last_positions: dict[str, dict] = {}
        self._position_max_interval = config.position_max_interval

        # Buffer configuration
        buffer_config = buffer_config or BufferConfig()
        self._flush_interval: float = buffer_config.flush_interval
        self._buffer_max_size: int = buffer_config.max_size
        self._message_buffer: list[dict] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._bootstrap_task: asyncio.Task | None = None
        self._bootstrap_lock = asyncio.Lock()
        self._bootstrap_pending: set[str] = set()

        # Event loop lag monitor
        self._lag_monitor_task: asyncio.Task | None = None

        # Thread pool for CPU-bound normalization (ELB.7)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="norm-")

        # Stats
        self._messages_received = 0
        self._positions_saved = 0
        self._positions_skipped = 0

        # Error channel rate-limiting — prevents log flooding from Hyperliquid
        # "Cannot track more than 10 total users" errors which can arrive at
        # hundreds per second and block the event loop with synchronous I/O.
        self._error_channel_count = 0
        self._error_channel_last_log: float = 0.0  # monotonic timestamp

    async def start(self, traders: list[str] | None = None) -> None:
        """Start the collector with specified traders.

        Args:
            traders: List of trader addresses to track (optional)
        """
        if self._running:
            logger.warning("trader_ws_already_running")
            return

        self._tracked_traders = [str(t).lower() for t in (traders or []) if t]
        self._running = True

        logger.info(
            "trader_ws_starting",
            num_traders=len(self._tracked_traders),
            num_clients=self._num_clients,
            symbol=self.config.symbol,
            flush_interval=self._flush_interval,
            buffer_max_size=self._buffer_max_size,
        )

        # Start flush loop even if there are no traders yet. This ensures
        # later `add_trader()` calls still get periodic flush behavior.
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

        # Start event loop lag monitor
        if self._lag_monitor_task is None:
            self._lag_monitor_task = asyncio.create_task(self._monitor_loop_lag())

        if not self._tracked_traders:
            logger.warning("no_traders_to_track")
            return

        # Split traders among clients
        trader_batches = [
            self._tracked_traders[i : i + self._batch_size]
            for i in range(0, len(self._tracked_traders), self._batch_size)
        ]

        # Determine how many clients we need (limited by _num_clients max)
        # Each client handles up to _batch_size traders
        num_needed_clients = len(trader_batches)
        num_clients_to_create = min(num_needed_clients, self._num_clients)

        # Create and start clients
        # If we have more batches than clients, later batches will be assigned
        # to clients when they have room (via add_trader)
        for i, batch in enumerate(trader_batches[:num_clients_to_create]):
            client = TraderWSClient(
                client_id=i,
                traders=batch,
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
                config=self.config,
            )
            self._clients.append(client)

        # Start all clients
        start_tasks = [client.start() for client in self._clients]
        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        logger.info("trader_ws_clients_started", successful=successful, total=len(self._clients))
        self._schedule_bootstrap(self._tracked_traders)

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        logger.info("trader_ws_stopping")
        self._running = False

        # Stop flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_flush_task_cancelled")

        # Stop lag monitor task
        if self._lag_monitor_task:
            self._lag_monitor_task.cancel()
            try:
                await self._lag_monitor_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_lag_monitor_cancelled")

        if self._bootstrap_task:
            self._bootstrap_task.cancel()
            try:
                await self._bootstrap_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_bootstrap_task_cancelled")

        # Flush remaining messages
        await self._flush_messages()

        # Stop all clients
        stop_tasks = [client.stop() for client in self._clients]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._clients.clear()
        logger.info("trader_ws_stopped", stats=self.get_stats())

    async def add_trader(self, address: str) -> None:
        """Add a trader to be tracked.

        Args:
            address: Trader's Ethereum address
        """
        address = str(address).lower()
        if address in self._tracked_traders:
            return

        if not self._running:
            await self.start([address])
            return

        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

        self._tracked_traders.append(address)

        # Add to first available client with space
        for client in self._clients:
            if len(client.traders) < self._batch_size:
                await client.subscribe_trader(address)
                return

        # Need to create new client
        if len(self._clients) < self._num_clients:
            client = TraderWSClient(
                client_id=len(self._clients),
                traders=[address],
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
                config=self.config,
            )
            self._clients.append(client)
            await client.start()

        self._schedule_bootstrap([address])

    async def remove_trader(self, address: str) -> None:
        """Remove a trader from tracking.

        Args:
            address: Trader's Ethereum address
        """
        address = str(address).lower()
        if address in self._tracked_traders:
            self._tracked_traders.remove(address)

        # Remove from clients
        for client in self._clients:
            if address in client.traders:
                await client.unsubscribe_trader(address)

    async def sync_traders(self, addresses: list[str]) -> dict[str, int]:
        """Reconcile tracked subscriptions against a desired address set.

        Args:
            addresses: Desired tracked addresses (will be normalized to lowercase)

        Returns:
            Summary with keys: added, removed, total
        """
        desired = {str(a).lower() for a in (addresses or []) if a}

        # Ensure collector is running so we can apply the reconciliation.
        if not self._running:
            await self.start(sorted(desired))
            return {"added": len(desired), "removed": 0, "total": len(desired)}

        current = {str(a).lower() for a in self._tracked_traders if a}

        to_remove = sorted(current - desired)
        to_add = sorted(desired - current)

        for addr in to_remove:
            await self.remove_trader(addr)
        for addr in to_add:
            await self.add_trader(addr)

        return {"added": len(to_add), "removed": len(to_remove), "total": len(desired)}

    def _schedule_bootstrap(self, addresses: list[str]) -> None:
        """Schedule reconciliation bootstrap for tracked trader addresses."""
        for address in addresses:
            normalized = str(address).lower()
            if normalized:
                self._bootstrap_pending.add(normalized)

        if self._bootstrap_task and not self._bootstrap_task.done():
            return
        self._bootstrap_task = asyncio.create_task(self._run_bootstrap_queue())

    async def _run_bootstrap_queue(self) -> None:
        """Drain bootstrap pending queue with coalescing."""
        while self._running:
            async with self._bootstrap_lock:
                if not self._bootstrap_pending:
                    return
                batch = sorted(self._bootstrap_pending)
                self._bootstrap_pending.clear()
                await self._bootstrap_reconcile(batch)

    async def _bootstrap_reconcile(self, addresses: list[str]) -> None:
        """Fetch current trader state from Hyperliquid HTTP API and emit snapshots.

        This seeds/corrects current-state rows so unknown/stale states converge
        even when WebSocket updates were missed.

        Processes traders in chunks of 25 with a 2-second pause between
        chunks to avoid flooding the API and triggering 429 rate-limits.
        """
        normalized = sorted({str(address).lower() for address in addresses if address})
        if not normalized:
            return

        logger.info("trader_ws_bootstrap_start", addresses=len(normalized))

        # Reduced concurrency: max 5 concurrent traders (10 HTTP requests)
        sem = asyncio.Semaphore(5)
        timeout = aiohttp.ClientTimeout(total=25)

        # Process traders in chunks with a pause between them to avoid API flood
        CHUNK_SIZE = 25
        all_events: list[StandardEvent] = []
        total_errors = 0

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for chunk_start in range(0, len(normalized), CHUNK_SIZE):
                chunk = normalized[chunk_start : chunk_start + CHUNK_SIZE]
                if chunk_start > 0:
                    await asyncio.sleep(2)  # Pause between chunks to avoid 429 flood
                tasks = [self._fetch_bootstrap_event(session, sem, address) for address in chunk]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        total_errors += 1
                        continue
                    if result is not None:
                        all_events.append(result)

        events = all_events

        if events:
            if self._on_bootstrap_event:
                # Reduced from 25 to 10 to limit concurrent handler pressure
                sem_direct = asyncio.Semaphore(10)

                async def handle_direct(event: StandardEvent) -> None:
                    async with sem_direct:
                        try:
                            result = self._on_bootstrap_event(event)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as exc:
                            logger.warning(
                                "trader_ws_bootstrap_direct_handler_failed",
                                event_id=event.event_id,
                                error=str(exc),
                            )

                await asyncio.gather(*(handle_direct(event) for event in events))
            await self.event_bus.publish_bulk(events)
            logger.info("trader_ws_bootstrap_published", events=len(events), errors=total_errors)
        else:
            logger.info("trader_ws_bootstrap_no_events", errors=total_errors)

    async def _fetch_bootstrap_event(
        self,
        session: aiohttp.ClientSession,
        sem: asyncio.Semaphore,
        address: str,
    ) -> StandardEvent | None:
        """Fetch one trader state snapshot from Hyperliquid info API.

        Uses the class-level rate limiter to cap at ~10 req/s and applies
        429-specific exponential backoff (2s, 4s, 8s) with Retry-After
        header support.  Non-429 errors use shorter retry delays.
        """
        payload = {"type": "clearinghouseState", "user": address}

        async with sem:
            for attempt in range(3):
                try:
                    # Rate-limit: wait for a slot before issuing the request
                    await self._api_rate_limiter.acquire()
                    async with session.post(
                        "https://api.hyperliquid.xyz/info", json=payload
                    ) as response:
                        if response.status == 429:
                            retry_after = float(response.headers.get("Retry-After", 0))
                            backoff = max(retry_after, 2.0 * (2 ** attempt))  # 2s, 4s, 8s
                            logger.warning(
                                "trader_ws_bootstrap_429",
                                address=address[:10],
                                attempt=attempt,
                                backoff_s=backoff,
                            )
                            if attempt == 2:
                                return None
                            await asyncio.sleep(backoff)
                            continue
                        if response.status != 200:
                            raise RuntimeError(f"status={response.status}")
                        clearinghouse_state = await response.json()

                    # Rate-limit second request too
                    await self._api_rate_limiter.acquire()
                    async with session.post(
                        "https://api.hyperliquid.xyz/info",
                        json={"type": "openOrders", "user": address},
                    ) as response:
                        if response.status == 429:
                            retry_after = float(response.headers.get("Retry-After", 0))
                            backoff = max(retry_after, 2.0 * (2 ** attempt))
                            logger.warning(
                                "trader_ws_bootstrap_429_open_orders",
                                address=address[:10],
                                attempt=attempt,
                                backoff_s=backoff,
                            )
                            if attempt == 2:
                                return None
                            await asyncio.sleep(backoff)
                            continue
                        if response.status != 200:
                            raise RuntimeError(f"open_orders_status={response.status}")
                        open_orders_data = await response.json()

                    positions = clearinghouse_state.get("assetPositions", [])
                    if not isinstance(positions, list):
                        positions = []
                    active_positions = [
                        p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0
                    ]
                    symbol_positions = [
                        p
                        for p in active_positions
                        if p.get("position", {}).get("coin") == self.config.symbol
                    ]
                    symbol_open_orders = self._filter_symbol_open_orders(open_orders_data)
                    margin_summary = clearinghouse_state.get("marginSummary", {})
                    return self._create_trader_positions_event(
                        address=address,
                        symbol_positions=symbol_positions,
                        open_orders=symbol_open_orders,
                        margin_summary=margin_summary if isinstance(margin_summary, dict) else {},
                        allow_empty=True,
                    )
                except Exception as exc:
                    if attempt == 2:
                        logger.warning(
                            "trader_ws_bootstrap_fetch_failed",
                            address=address[:10],
                            error=str(exc),
                        )
                        return None
                    # Non-429 errors: short retry (0.5s, 1.0s, 1.5s)
                    await asyncio.sleep(0.5 * (attempt + 1))

            return None

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming WebSocket message.

        Args:
            data: Parsed message data
        """
        self._messages_received += 1

        # Filter error channel messages (e.g. "Cannot track more than 10 total users.")
        # These have channel="error" and data is a string, not a dict — skip them entirely
        # to prevent AttributeError crashes downstream.
        # Rate-limited: only log once per 60s with count to avoid flooding the event loop.
        if data.get("channel") == "error":
            self._error_channel_count += 1
            now = time.monotonic()
            if now - self._error_channel_last_log >= 60.0:
                logger.warning(
                    "trader_ws_server_error",
                    error_data=data.get("data"),
                    count=self._error_channel_count,
                    suppressed=self._error_channel_count - 1,
                )
                self._error_channel_count = 0
                self._error_channel_last_log = now
            return

        # Debug: Log message receipt
        if self._messages_received <= 5:
            msg_data = data.get("data", {})
            has_user = bool(msg_data.get("user")) if isinstance(msg_data, dict) else False
            logger.debug(
                "trader_ws_message_received",
                msg_num=self._messages_received,
                channel=data.get("channel"),
                has_user=has_user,
            )

        should_flush = False
        async with self._buffer_lock:
            self._message_buffer.append(data)

            # Check if buffer is full
            if len(self._message_buffer) >= self._buffer_max_size:
                logger.debug("trader_ws_buffer_full_flushing", size=len(self._message_buffer))
                should_flush = True

        # Flush outside the lock to avoid deadlock
        if should_flush:
            await self._flush_messages()

    async def _handle_disconnect(self, client_id: int) -> None:
        """Handle client disconnection.

        Args:
            client_id: ID of disconnected client
        """
        logger.warning("trader_ws_client_disconnected", client_id=client_id)

        # Find and recreate the client
        for i, client in enumerate(self._clients):
            if client.client_id == client_id:
                # Stop old client
                try:
                    await client.stop()
                except Exception as e:
                    logger.debug("trader_ws_client_stop_error", client_id=client_id, error=str(e))

                # Get traders for this client
                traders = client.traders

                if traders and self._running:
                    # Wait before reconnecting
                    await asyncio.sleep(5)

                    # Create new client
                    new_client = TraderWSClient(
                        client_id=client_id,
                        traders=traders,
                        on_message=self._handle_message,
                        on_disconnect=self._handle_disconnect,
                        config=self.config,
                    )
                    self._clients[i] = new_client
                    await new_client.start()

                break

    async def _flush_loop(self) -> None:
        """Periodically flush the message buffer."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush_messages()

    async def _monitor_loop_lag(self) -> None:
        """Monitor event loop lag and log warnings if excessive."""
        while self._running:
            start = time.monotonic()
            await asyncio.sleep(1)
            lag = time.monotonic() - start - 1.0

            if lag > 2.0:
                logger.error(
                    "event_loop_lag_critical",
                    lag_ms=round(lag * 1000, 1),
                )
            elif lag > 0.5:
                logger.warning(
                    "event_loop_lag_high",
                    lag_ms=round(lag * 1000, 1),
                )

    def _serialize_for_comparison(self, value: Any) -> Any:
        """Recursively normalize a payload for deterministic comparisons."""
        if isinstance(value, dict):
            return {
                str(key): self._serialize_for_comparison(val)
                for key, val in sorted(value.items())
            }
        if isinstance(value, list):
            return [self._serialize_for_comparison(item) for item in value]
        if isinstance(value, float):
            return round(value, 10)
        return value

    def _normalize_positions(self, positions: list[dict] | None) -> str:
        """Normalize positions for comparison.

        Args:
            positions: List of position data

        Returns:
            Normalized string for comparison
        """
        if not positions:
            return ""

        # Sort by coin for consistent comparison
        sorted_positions = sorted(
            positions,
            key=lambda x: str(
                (x.get("position", x) if isinstance(x, dict) else {}).get("coin", "")
            ),
        )

        return json.dumps(
            self._serialize_for_comparison(sorted_positions),
            sort_keys=True,
            separators=(",", ":"),
        )

    def _normalize_margin_summary(self, margin_summary: dict[str, Any] | None) -> str:
        """Normalize margin summary payload for deterministic comparisons."""
        if not margin_summary:
            return ""

        return json.dumps(
            self._serialize_for_comparison(margin_summary),
            sort_keys=True,
            separators=(",", ":"),
        )

    def _normalize_open_orders(self, open_orders: list[dict] | None) -> str:
        """Normalize open orders payload for deterministic comparisons."""
        if not open_orders:
            return ""

        sorted_orders = sorted(
            open_orders,
            key=lambda order: (
                str((order or {}).get("coin", "")),
                str((order or {}).get("oid", "")),
                str((order or {}).get("side", "")),
                str((order or {}).get("timestamp", "")),
            ),
        )

        return json.dumps(
            self._serialize_for_comparison(sorted_orders),
            sort_keys=True,
            separators=(",", ":"),
        )

    def _has_significant_change(
        self,
        address: str,
        positions: list[dict],
        open_orders: list[dict] | None = None,
        margin_summary: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, str]]:
        """Check if positions have changed significantly.

        Args:
            address: Trader address
            positions: Current positions
            open_orders: Current open orders
            margin_summary: Latest margin summary

        Returns:
            Tuple of (should_save, computed_values) where computed_values
            contains pre-computed normalized strings for reuse.
        """
        # Compute normalized strings once for both comparison and caching
        current_normalized = self._normalize_positions(positions)
        current_open_orders = self._normalize_open_orders(open_orders)
        current_margin_summary = self._normalize_margin_summary(margin_summary)

        last_saved = self._last_positions.get(address, {})

        # Check time since last save (safety interval)
        last_time = last_saved.get("timestamp", 0)
        time_since_save = time.time() - last_time

        # Compute SHA-256 hash once for both comparison and storage
        current_hash = hashlib.sha256(
            (current_normalized + current_open_orders + current_margin_summary).encode()
        ).hexdigest()
        last_hash = last_saved.get("hash", "")

        computed = {
            "hash": current_hash,
            "normalized": current_normalized,
            "open_orders": current_open_orders,
            "margin_summary": current_margin_summary,
        }

        if time_since_save >= self._position_max_interval:
            return True, computed

        if last_hash != current_hash:
            return True, computed

        return False, {}


    def _normalize_batch(self, items: list[tuple[list, list, dict]]) -> list[tuple[str, str, str]]:
        """Normalize a batch of (positions, open_orders, margin_summary) tuples.

        CPU-bound work meant to run in a thread pool executor.
        Returns list of (normalized_pos, normalized_orders, normalized_margin) strings.
        """
        return [
            (
                self._normalize_positions(pos),
                self._normalize_open_orders(ords),
                self._normalize_margin_summary(marg),
            )
            for pos, ords, marg in items
        ]

    def _cleanup_stale_positions(self) -> None:
        """Remove stale position entries to prevent unbounded memory growth."""
        now = time.time()
        cutoff = now - self.POSITION_STATE_TTL

        stale_addresses = [
            addr for addr, data in self._last_positions.items()
            if data.get("timestamp", 0) < cutoff
        ]

        for addr in stale_addresses:
            del self._last_positions[addr]

        # Enforce max size
        if len(self._last_positions) > self.MAX_TRACKED_POSITIONS:
            sorted_items = sorted(
                self._last_positions.items(),
                key=lambda x: x[1].get("timestamp", 0),
            )
            for addr, _ in sorted_items[:len(self._last_positions) - self.MAX_TRACKED_POSITIONS]:
                del self._last_positions[addr]

        if stale_addresses:
            logger.debug(
                "position_state_cleanup",
                removed=len(stale_addresses),
                remaining=len(self._last_positions),
            )

    async def _flush_messages(self) -> None:
        """Flush buffered messages and emit events."""
        flush_start = time.monotonic()

        async with self._buffer_lock:
            if not self._message_buffer:
                return

            messages = self._message_buffer.copy()
            self._message_buffer.clear()

        # Cleanup stale position state periodically
        self._cleanup_stale_positions()

        events: list[StandardEvent] = []
        webdata_count = 0
        CHUNK_SIZE = 200

        # Process messages in chunks to yield control more frequently
        for chunk_start in range(0, len(messages), CHUNK_SIZE):
            chunk = messages[chunk_start : chunk_start + CHUNK_SIZE]

            # Collect webData2 messages and pre-extract their data
            webdata_msgs = []
            for msg in chunk:
                if msg.get("channel") == "webData2":
                    webdata_count += 1
                    webdata_msgs.append(msg)

            # Offload CPU-heavy normalization to thread pool in sub-chunks
            NORM_CHUNK = 50
            for norm_start in range(0, len(webdata_msgs), NORM_CHUNK):
                norm_chunk = webdata_msgs[norm_start : norm_start + NORM_CHUNK]
                norm_items = []
                for msg in norm_chunk:
                    data = msg.get("data", {})
                    # Safety guard: skip messages where data is not a dict (e.g. error channel)
                    if not isinstance(data, dict):
                        continue
                    address = str(data.get("user", "")).lower()
                    clearinghouse = data.get("clearinghouseState", {})
                    positions = clearinghouse.get("assetPositions", [])
                    open_orders = data.get("openOrders", [])
                    margin_summary = clearinghouse.get("marginSummary", {})
                    if not isinstance(positions, list):
                        positions = []
                    active_positions = [p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0]
                    symbol_positions = [p for p in active_positions if p.get("position", {}).get("coin") == self.config.symbol]
                    symbol_open_orders = self._filter_symbol_open_orders(open_orders)
                    if not isinstance(margin_summary, dict):
                        margin_summary = {}
                    norm_items.append((address, symbol_positions, symbol_open_orders, margin_summary))

                # Run CPU-bound normalization in thread pool
                raw_items = [(sp, so, ms) for _, sp, so, ms in norm_items]
                normalized_results = await asyncio.get_event_loop().run_in_executor(
                    self._executor, self._normalize_batch, raw_items
                )

                # Now do the async-side comparison and event creation with pre-computed norms
                for (address, symbol_positions, symbol_open_orders, margin_summary), (norm_pos, norm_ords, norm_margin) in zip(norm_items, normalized_results):
                    event = self._create_trader_positions_event_normalized(
                        address, symbol_positions, symbol_open_orders, margin_summary,
                        norm_pos, norm_ords, norm_margin, allow_empty=False,
                    )
                    if event:
                        events.append(event)

                # Yield after each normalization sub-chunk
                await asyncio.sleep(0)

            # Handle non-webData2 messages (if any)
            for msg in chunk:
                if msg.get("channel") != "webData2":
                    event = self._process_webdata2(msg)
                    if event:
                        events.append(event)

            # Yield control after each chunk
            await asyncio.sleep(0)

        logger.debug(
            "trader_ws_flush_processed",
            total_messages=len(messages),
            webdata_messages=webdata_count,
            events_created=len(events),
            positions_saved=self._positions_saved,
            positions_skipped=self._positions_skipped,
        )

        # Publish events in chunks
        for pub_start in range(0, len(events), CHUNK_SIZE):
            chunk_events = events[pub_start : pub_start + CHUNK_SIZE]
            await self.event_bus.publish_bulk(chunk_events)
            await asyncio.sleep(0)

        if events:
            logger.info("trader_ws_events_published", count=len(events))

        # Clear buffer references for GC before method returns
        del messages

        flush_duration = time.monotonic() - flush_start
        logger.info(
            "trader_ws_flush_complete",
            duration_ms=round(flush_duration * 1000, 1),
            messages=len(events) + webdata_count,  # approximate since messages is deleted
            events=len(events),
        )

    def _process_webdata2(self, msg: dict) -> StandardEvent | None:
        """Process webData2 message and create event.

        Args:
            msg: WebSocket message

        Returns:
            StandardEvent or None if filtered
        """
        # Safety guard: skip messages where data is not a dict (e.g. error channel messages)
        data = msg.get("data", {})
        if not isinstance(data, dict):
            return None
        address = str(data.get("user", "")).lower()
        clearinghouse = data.get("clearinghouseState", {})
        positions = clearinghouse.get("assetPositions", [])
        open_orders = data.get("openOrders", [])
        margin_summary = clearinghouse.get("marginSummary", {})

        if not address:
            return None
        if not isinstance(positions, list):
            positions = []

        # Filter for active positions
        active_positions = [p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0]

        # BTC-ONLY FILTER: Only process positions for configured symbol
        symbol_positions = [
            p for p in active_positions if p.get("position", {}).get("coin") == self.config.symbol
        ]
        symbol_open_orders = self._filter_symbol_open_orders(open_orders)
        return self._create_trader_positions_event(
            address=address,
            symbol_positions=symbol_positions,
            open_orders=symbol_open_orders,
            margin_summary=margin_summary if isinstance(margin_summary, dict) else {},
            allow_empty=False,
        )

    def _filter_symbol_open_orders(self, open_orders: Any) -> list[dict]:
        """Filter open orders to active configured-symbol orders."""
        if not isinstance(open_orders, list):
            return []

        symbol = str(self.config.symbol).upper()
        symbol_orders: list[dict] = []
        for order in open_orders:
            if not isinstance(order, dict):
                continue
            if str(order.get("coin", "")).upper() != symbol:
                continue
            try:
                size = float(order.get("sz", 0) or 0)
            except (TypeError, ValueError):
                size = 0.0
            if size <= 0:
                continue
            symbol_orders.append(order)
        return symbol_orders

    def _create_trader_positions_event_normalized(
        self,
        address: str,
        symbol_positions: list[dict],
        open_orders: list[dict],
        margin_summary: dict[str, Any],
        norm_positions: str,
        norm_open_orders: str,
        norm_margin: str,
        allow_empty: bool = False,
    ) -> StandardEvent | None:
        """Create trader position event using pre-computed normalizations (avoids re-computation)."""
        if not symbol_positions and not open_orders and not allow_empty and address not in self._last_positions:
            self._positions_skipped += 1
            return None

        changed, computed = self._has_significant_change_normalized(
            address, norm_positions, norm_open_orders, norm_margin
        )
        if not changed:
            self._positions_skipped += 1
            return None

        self._positions_saved += 1
        logger.debug(
            "trader_ws_position_saved",
            address=address[:10],
            symbol=self.config.symbol,
            position_count=len(symbol_positions),
        )

        combined_hash = computed.get("hash", "")
        self._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time(),
        }

        return StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_trader_ws",
            payload={
                "address": address,
                "symbol": self.config.symbol,
                "positions": symbol_positions,
                "openOrders": open_orders,
                "marginSummary": margin_summary,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def _has_significant_change_normalized(
        self,
        address: str,
        norm_positions: str,
        norm_open_orders: str,
        norm_margin: str,
    ) -> tuple[bool, dict[str, str]]:
        """Check for significant change using pre-computed normalized strings."""
        last_saved = self._last_positions.get(address, {})
        last_time = last_saved.get("timestamp", 0)
        time_since_save = time.time() - last_time

        current_hash = hashlib.sha256(
            (norm_positions + norm_open_orders + norm_margin).encode()
        ).hexdigest()
        last_hash = last_saved.get("hash", "")

        computed = {
            "hash": current_hash,
            "normalized": norm_positions,
            "open_orders": norm_open_orders,
            "margin_summary": norm_margin,
        }

        if time_since_save >= self._position_max_interval:
            return True, computed

        if last_hash != current_hash:
            return True, computed

        return False, {}

    def _create_trader_positions_event(
        self,
        address: str,
        symbol_positions: list[dict],
        open_orders: list[dict],
        margin_summary: dict[str, Any],
        allow_empty: bool,
    ) -> StandardEvent | None:
        """Create trader position event with change detection and state tracking."""
        if not symbol_positions and not open_orders and not allow_empty and address not in self._last_positions:
            self._positions_skipped += 1
            return None

        changed, computed = self._has_significant_change(address, symbol_positions, open_orders, margin_summary)
        if not changed:
            self._positions_skipped += 1
            return None

        self._positions_saved += 1
        logger.debug(
            "trader_ws_position_saved",
            address=address[:10],
            symbol=self.config.symbol,
            position_count=len(symbol_positions),
        )

        # Store only the SHA-256 hash instead of raw data + normalized strings
        normalized = computed.get("normalized", "")
        open_orders_str = computed.get("open_orders", "")
        margin_summary_str = computed.get("margin_summary", "")
        combined_hash = computed.get("hash", "")

        self._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time(),
        }

        return StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_trader_ws",
            payload={
                "address": address,
                "symbol": self.config.symbol,
                "positions": symbol_positions,
                "openOrders": open_orders,
                "marginSummary": margin_summary,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "running": self._running,
            "tracked_traders": len(self._tracked_traders),
            "active_clients": len(self._clients),
            "connected_clients": sum(1 for c in self._clients if c.is_connected),
            "messages_received": self._messages_received,
            "positions_saved": self._positions_saved,
            "positions_skipped": self._positions_skipped,
            "error_channel_count": self._error_channel_count,
            "buffer_size": len(self._message_buffer),
        }


class TraderWSClient:
    """Single WebSocket client for a batch of traders."""

    def __init__(
        self,
        client_id: int,
        traders: list[str],
        on_message: Callable[[dict], None],
        on_disconnect: Callable[[int], None],
        config: HyperliquidSettings,
    ) -> None:
        """Initialize the client.

        Args:
            client_id: Client identifier
            traders: List of trader addresses to subscribe
            on_message: Callback for messages
            on_disconnect: Callback for disconnection
            config: Hyperliquid settings
        """
        self.client_id = client_id
        self.traders = traders
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.config = config

        self._session: aiohttp.ClientSession | None = None
        self._session_closed = False
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._reconnect_attempts = 0
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> bool:
        """Start the WebSocket client.

        Returns:
            True if started successfully
        """
        try:
            self._running = True
            self._session = aiohttp.ClientSession()
            self._session_closed = False

            self._ws = await self._session.ws_connect(
                TraderWebSocketCollector.WS_URL,
                heartbeat=self.config.heartbeat_interval,
            )

            logger.info("trader_ws_client_connected", client_id=self.client_id)

            # Subscribe to all traders
            # Guard against writing to a closing transport — check ws.closed
            # before each send_json. If the WS closes mid-subscription, raise
            # to trigger proper backoff reconnect (instead of a rapid 1s loop).
            for address in self.traders:
                if self._ws.closed:
                    raise ConnectionError(
                        "WebSocket closed before subscription completed"
                    )
                await self._ws.send_json(
                    {
                        "method": "subscribe",
                        "subscription": {"type": "webData2", "user": address},
                    }
                )
                await asyncio.sleep(0.01)  # Small delay between subscriptions

            # Only reset reconnect counter after full subscription success
            # Previously this was set right after ws_connect, which caused
            # only 1s backoff when send_json failed on a closing transport.
            self._reconnect_attempts = 0

            logger.info(
                "trader_ws_client_subscribed",
                client_id=self.client_id,
                traders=len(self.traders),
            )

            # Start listening
            self._listen_task = asyncio.create_task(self._listen())

            return True

        except Exception as e:
            logger.error(
                "trader_ws_client_start_error",
                client_id=self.client_id,
                error=str(e),
                exc_info=True,
            )
            await self._handle_error()
            return False

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_listen_task_cancelled", client_id=self.client_id)

        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug("trader_ws_close_error", client_id=self.client_id, error=str(e))

        # Close session with proper error handling
        if self._session and not self._session_closed:
            try:
                await self._session.close()
                self._session_closed = True
            except Exception as e:
                logger.error("trader_ws_session_close_error", client_id=self.client_id, error=str(e))
            finally:
                self._session = None

        logger.info("trader_ws_client_stopped", client_id=self.client_id)

    async def subscribe_trader(self, address: str) -> None:
        """Subscribe to a trader.

        Args:
            address: Trader's Ethereum address
        """
        if address not in self.traders:
            self.traders.append(address)

        if self._ws and not self._ws.closed:
            await self._ws.send_json(
                {
                    "method": "subscribe",
                    "subscription": {"type": "webData2", "user": address},
                }
            )

    async def unsubscribe_trader(self, address: str) -> None:
        """Unsubscribe from a trader.

        Args:
            address: Trader's Ethereum address
        """
        if address in self.traders:
            self.traders.remove(address)

        if self._ws and not self._ws.closed:
            await self._ws.send_json(
                {
                    "method": "unsubscribe",
                    "subscription": {"type": "webData2", "user": address},
                }
            )

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self._running and self._ws:
            try:
                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self.on_message(data)

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning("trader_ws_client_connection_lost", client_id=self.client_id)
                    await self._handle_error()
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "trader_ws_client_listen_error",
                    client_id=self.client_id,
                    error=str(e),
                    exc_info=True,
                )
                await self._handle_error()
                break

    async def _handle_error(self) -> None:
        """Handle connection errors with reconnection."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self.config.reconnect_max_attempts:
            logger.error(
                "trader_ws_client_max_reconnect",
                client_id=self.client_id,
            )
            await self.on_disconnect(self.client_id)
            return

        # Exponential backoff with a minimum floor of 2s to prevent
        # rapid reconnection storms that block the event loop.
        # With 30+ WS clients all reconnecting at 1s, the event loop
        # gets overwhelmed and HTTP becomes unresponsive.
        raw_delay = self.config.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1))
        delay = max(2.0, min(raw_delay, self.config.reconnect_max_delay))

        logger.info(
            "trader_ws_client_reconnecting",
            client_id=self.client_id,
            delay=delay,
            attempt=self._reconnect_attempts,
        )

        await asyncio.sleep(delay)

        # Cleanup and restart
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug("trader_ws_close_error", client_id=self.client_id, error=str(e))

        # Close session before reconnecting
        if self._session and not self._session_closed:
            try:
                await self._session.close()
                self._session_closed = True
            except Exception as e:
                logger.debug("trader_ws_session_cleanup_error", client_id=self.client_id, error=str(e))
            finally:
                self._session = None

        await self.start()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._ws is not None and not self._ws.closed
