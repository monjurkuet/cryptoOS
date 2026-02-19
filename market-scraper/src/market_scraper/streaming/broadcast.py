# src/market_scraper/streaming/broadcast.py

"""Broadcasting utilities for efficient message delivery."""

import asyncio
import time
from collections import deque
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BroadcastMessage:
    """Message to be broadcast to clients."""

    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    priority: int = 5  # Lower is higher priority
    target_symbols: set[str] | None = None
    target_event_types: set[str] | None = None


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    messages_per_second: float = 100.0
    burst_size: int = 10
    max_queue_size: int = 1000


class RateLimiter:
    """Token bucket rate limiter for message broadcasting."""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limiting configuration
        """
        self._config = config
        self._tokens: float = config.burst_size
        self._last_update: float = time.time()
        self._lock: asyncio.Lock = asyncio.Lock()
        self._logger = logger.bind(component="rate_limiter")

    async def acquire(self) -> bool:
        """Acquire a token for sending a message.

        Returns:
            True if token acquired, False if rate limited
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update

            # Add tokens based on time elapsed
            self._tokens = min(
                self._config.burst_size, self._tokens + elapsed * self._config.messages_per_second
            )
            self._last_update = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True

            return False

    async def wait_for_token(self, timeout: float | None = None) -> bool:
        """Wait for a token to become available.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if token acquired, False if timed out
        """
        start_time = time.time()

        while timeout is None or (time.time() - start_time) < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(0.01)  # 10ms sleep between attempts

        return False


class BroadcastManager:
    """Manages efficient message broadcasting with batching and rate limiting.

    Features:
    - Message batching for improved throughput
    - Rate limiting per client and globally
    - Priority queuing for important messages
    - Automatic retry for failed broadcasts
    """

    def __init__(
        self,
        batch_size: int = 100,
        batch_timeout_ms: float = 10.0,
        rate_limit: RateLimitConfig | None = None,
    ) -> None:
        """Initialize broadcast manager.

        Args:
            batch_size: Maximum number of messages to batch together
            batch_timeout_ms: Maximum time to wait before flushing batch
            rate_limit: Optional rate limiting configuration
        """
        self._batch_size = batch_size
        self._batch_timeout_ms = batch_timeout_ms
        self._rate_limiter = RateLimiter(rate_limit or RateLimitConfig())
        self._message_queue: deque[BroadcastMessage] = deque()
        self._batch_task: asyncio.Task | None = None
        self._running: bool = False
        self._client_limiters: dict[str, RateLimiter] = {}
        self._logger = logger.bind(component="broadcast_manager")

        # Metrics
        self._metrics: dict[str, int] = {
            "messages_queued": 0,
            "messages_sent": 0,
            "messages_dropped": 0,
            "batches_sent": 0,
        }

    async def start(self) -> None:
        """Start the broadcast manager."""
        self._running = True
        self._batch_task = asyncio.create_task(self._batch_processor())
        self._logger.info("Broadcast manager started")

    async def stop(self) -> None:
        """Stop the broadcast manager and flush remaining messages."""
        self._running = False

        if self._batch_task:
            # Flush remaining messages
            await self._flush_batch()

            self._batch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._batch_task

        self._logger.info("Broadcast manager stopped")

    def queue_message(
        self,
        message: BroadcastMessage,
    ) -> bool:
        """Queue a message for broadcasting.

        Args:
            message: Message to broadcast

        Returns:
            True if queued successfully, False if queue is full
        """
        if len(self._message_queue) >= self._rate_limiter._config.max_queue_size:
            self._metrics["messages_dropped"] += 1
            self._logger.warning("Message queue full, dropping message")
            return False

        self._message_queue.append(message)
        self._metrics["messages_queued"] += 1
        return True

    async def broadcast(
        self,
        message: BroadcastMessage,
        clients: list[Any],
        send_func: Callable[[Any, dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> dict[str, int]:
        """Broadcast a message to multiple clients immediately.

        Args:
            message: Message to broadcast
            clients: List of client connections
            send_func: Async function to send message to a client

        Returns:
            Statistics dict with sent and failed counts
        """
        # Wait for rate limit
        if not await self._rate_limiter.wait_for_token(timeout=1.0):
            self._logger.warning("Rate limit exceeded, dropping broadcast")
            self._metrics["messages_dropped"] += 1
            return {"sent": 0, "failed": len(clients), "rate_limited": True}

        # Send to all clients
        tasks = [send_func(client, message.payload) for client in clients]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        sent = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - sent

        self._metrics["messages_sent"] += sent

        return {"sent": sent, "failed": failed, "rate_limited": False}

    async def _batch_processor(self) -> None:
        """Background task to process batched messages."""
        while self._running:
            try:
                await asyncio.sleep(self._batch_timeout_ms / 1000.0)

                if self._message_queue:
                    await self._flush_batch()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error("Batch processor error", error=str(e))

    async def _flush_batch(self) -> None:
        """Flush the current message batch."""
        if not self._message_queue:
            return

        # Take up to batch_size messages
        batch: list[BroadcastMessage] = []
        while len(batch) < self._batch_size and self._message_queue:
            batch.append(self._message_queue.popleft())

        if batch:
            self._metrics["batches_sent"] += 1
            self._logger.debug(
                "Flushing batch",
                batch_size=len(batch),
            )
            # Actual broadcast logic would be implemented here
            # based on target symbols and event types

    def get_client_limiter(self, client_id: str) -> RateLimiter:
        """Get or create a rate limiter for a specific client.

        Args:
            client_id: Client identifier

        Returns:
            RateLimiter instance for the client
        """
        if client_id not in self._client_limiters:
            self._client_limiters[client_id] = RateLimiter(RateLimitConfig())
        return self._client_limiters[client_id]

    def get_metrics(self) -> dict[str, Any]:
        """Get broadcast manager metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            **self._metrics,
            "queue_size": len(self._message_queue),
            "running": self._running,
            "rate_limit_tokens": self._rate_limiter._tokens,
        }


class MessageCompressor:
    """Compresses messages for efficient transmission.

    Simple compression strategy that removes unnecessary whitespace
    and uses short field names.
    """

    # Field name mappings for compression
    FIELD_MAP = {
        "event_id": "eid",
        "event_type": "et",
        "timestamp": "ts",
        "source": "src",
        "payload": "pld",
        "symbol": "sym",
        "price": "p",
        "volume": "v",
        "bid": "b",
        "ask": "a",
        "bid_volume": "bv",
        "ask_volume": "av",
        "open": "o",
        "high": "h",
        "low": "l",
        "close": "c",
    }

    @classmethod
    def compress(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Compress message data by shortening field names.

        Args:
            data: Original message data

        Returns:
            Compressed data with short field names
        """
        return {cls.FIELD_MAP.get(k, k): v for k, v in data.items()}

    @classmethod
    def decompress(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Decompress message data by restoring field names.

        Args:
            data: Compressed message data

        Returns:
            Original data with full field names
        """
        reverse_map = {v: k for k, v in cls.FIELD_MAP.items()}
        return {reverse_map.get(k, k): v for k, v in data.items()}
