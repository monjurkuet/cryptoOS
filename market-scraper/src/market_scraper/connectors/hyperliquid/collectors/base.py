# src/market_scraper/connectors/hyperliquid/collectors/base.py

"""Base collector class for Hyperliquid data collection."""

import asyncio
import contextlib
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

from market_scraper.config.market_config import BufferConfig
from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)


class BaseCollector(ABC):
    """Abstract base class for Hyperliquid data collectors.

    Collectors receive WebSocket messages, filter/transform them,
    and emit StandardEvents to the event bus.

    Attributes:
        symbol: The symbol being tracked (only this symbol's data is saved)
        event_bus: Event bus for publishing events
        config: Hyperliquid settings
        _running: Whether the collector is actively processing
        _buffer: Buffer for batch event publishing
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
        buffer_config: BufferConfig | None = None,
    ) -> None:
        """Initialize the collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings (includes symbol filter)
            buffer_config: Buffer and flush configuration
        """
        self.event_bus = event_bus
        self.config = config
        self.symbol = config.symbol  # Only save this symbol's data
        self._running = False

        # Buffer configuration
        buffer_config = buffer_config or BufferConfig()
        self._buffer: list[StandardEvent] = []
        self._flush_interval: float = buffer_config.flush_interval
        self._buffer_max_size: int = buffer_config.max_size
        self._last_flush: float = time.time()
        self._flush_task: asyncio.Task | None = None

        # Metrics
        self._messages_received = 0
        self._messages_processed = 0
        self._messages_filtered = 0
        self._events_emitted = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Collector name for logging and metrics."""
        pass

    @property
    def is_running(self) -> bool:
        """Check if collector is running."""
        return self._running

    async def start(self) -> None:
        """Start the collector."""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "collector_started",
            collector=self.name,
            symbol=self.symbol,
            flush_interval=self._flush_interval,
            buffer_max_size=self._buffer_max_size,
        )

    async def stop(self) -> None:
        """Stop the collector and flush remaining events."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
        await self._flush_buffer()
        logger.info(
            "collector_stopped",
            collector=self.name,
            metrics=self.get_metrics(),
        )

    @abstractmethod
    async def handle_message(self, data: dict[str, Any]) -> list[StandardEvent]:
        """Process incoming WebSocket message.

        Args:
            data: Raw WebSocket message data

        Returns:
            List of StandardEvents to emit (may be empty if filtered)
        """
        pass

    async def process_message(self, data: dict[str, Any]) -> None:
        """Process a message and buffer events.

        This is the main entry point called by the WebSocket manager.

        Args:
            data: Raw WebSocket message data
        """
        self._messages_received += 1

        if not self._running:
            return

        try:
            events = await self.handle_message(data)

            if events:
                self._messages_processed += 1
                self._buffer.extend(events)
                self._events_emitted += len(events)

                # Flush if buffer is large
                if len(self._buffer) >= self._buffer_max_size:
                    await self._flush_buffer()
            else:
                self._messages_filtered += 1

        except Exception as e:
            logger.error(
                "collector_error",
                collector=self.name,
                error=str(e),
                exc_info=True,
            )

    async def _flush_loop(self) -> None:
        """Periodically flush the event buffer."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            if self._buffer:
                await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Flush buffered events to the event bus."""
        if not self._buffer:
            return

        events = self._buffer.copy()
        self._buffer.clear()

        try:
            count = await self.event_bus.publish_bulk(events)

            # Aggregate by interval for better visibility
            intervals: dict[str, int] = {}
            for event in events:
                interval = (
                    event.payload.get("interval", "unknown")
                    if isinstance(event.payload, dict)
                    else "unknown"
                )
                intervals[interval] = intervals.get(interval, 0) + 1

            logger.debug(
                "buffer_flushed",
                collector=self.name,
                events_published=count,
                intervals=intervals,
            )
        except Exception as e:
            logger.error(
                "flush_error",
                collector=self.name,
                error=str(e),
                events_lost=len(events),
                exc_info=True,
            )

    def get_metrics(self) -> dict[str, int]:
        """Get collector metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "messages_received": self._messages_received,
            "messages_processed": self._messages_processed,
            "messages_filtered": self._messages_filtered,
            "events_emitted": self._events_emitted,
            "buffer_size": len(self._buffer),
        }

    def _should_process_symbol(self, coin: str) -> bool:
        """Check if a symbol should be processed based on config.

        Args:
            coin: The coin/symbol from the message

        Returns:
            True if this symbol should be processed
        """
        # Normalize coin name (remove @ prefix if present)
        normalized = coin.lstrip("@")

        # Check if it matches our configured symbol
        return normalized == self.symbol
