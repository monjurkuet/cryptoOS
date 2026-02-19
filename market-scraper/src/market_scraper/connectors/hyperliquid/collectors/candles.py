# src/market_scraper/connectors/hyperliquid/collectors/candles.py

"""Candles collector for OHLCV data."""

from datetime import datetime
from typing import Any

import structlog

from market_scraper.connectors.hyperliquid.collectors.base import BaseCollector
from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)


class CandlesCollector(BaseCollector):
    """Collects candle (OHLCV) data from Hyperliquid WebSocket.

    Features:
    - Supports multiple intervals (1m, 5m, 15m, 1h, 4h, 1d)
    - Only processes configured symbol
    """

    # Supported intervals
    INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

    def __init__(self, event_bus: EventBus, config: HyperliquidSettings) -> None:
        """Initialize the candles collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
        """
        super().__init__(event_bus, config)
        self._active_intervals: set[str] = set()

    @property
    def name(self) -> str:
        """Collector name."""
        return "candles"

    async def handle_message(self, data: dict[str, Any]) -> list[StandardEvent]:
        """Process candles message.

        Args:
            data: WebSocket message with candle data

        Returns:
            List of candle events
        """
        events = []

        # Get candle data
        candle_data = data.get("data", {})
        if not candle_data:
            return []

        # Hyperliquid uses 's' for symbol and 'i' for interval in the data
        symbol = candle_data.get("s", "")

        # SYMBOL FILTER: Only process configured symbol
        if not self._should_process_symbol(symbol):
            return []

        # Get interval from data (Hyperliquid sends 'i' in data)
        interval = candle_data.get("i") or self._extract_interval(data)
        if not interval:
            return []

        # Create event
        event = self._create_candle_event(candle_data, interval)
        if event:
            events.append(event)
            self._active_intervals.add(interval)

        return events

    def _extract_interval(self, data: dict[str, Any]) -> str | None:
        """Extract interval from message (fallback method).

        Args:
            data: Raw message data

        Returns:
            Interval string or None
        """
        # Interval is usually in the data as 'i', but fallback to subscription
        candle_data = data.get("data", {})
        if isinstance(candle_data, dict) and "i" in candle_data:
            return candle_data.get("i")

        subscription = data.get("subscription", {})
        if isinstance(subscription, dict):
            return subscription.get("interval")

        return None

    def _create_candle_event(
        self,
        candle: dict[str, Any],
        interval: str,
    ) -> StandardEvent | None:
        """Create a StandardEvent from candle data.

        Args:
            candle: Raw candle data
            interval: Candle interval

        Returns:
            StandardEvent or None if invalid
        """
        try:
            timestamp = datetime.utcfromtimestamp(candle.get("t", 0) / 1000)

            return StandardEvent.create(
                event_type="ohlcv",
                source="hyperliquid",
                payload={
                    "symbol": self.symbol,
                    "timestamp": timestamp.isoformat(),
                    "interval": interval,
                    "open": float(candle.get("o", 0)),
                    "high": float(candle.get("h", 0)),
                    "low": float(candle.get("l", 0)),
                    "close": float(candle.get("c", 0)),
                    "volume": float(candle.get("v", 0)),
                },
            )
        except Exception as e:
            logger.warning(
                "candle_parse_error",
                error=str(e),
                candle=candle,
            )
            return None
