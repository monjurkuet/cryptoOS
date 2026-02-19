"""In-memory repository implementation for testing."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.core.types import Symbol, Timeframe
from market_scraper.storage.base import DataRepository, QueryFilter


class MemoryRepository(DataRepository):
    """In-memory implementation of DataRepository.

    Stores events in a list and provides query capabilities.
    Suitable for testing and development.

    Note: This implementation is not thread-safe and should not be used
    for production workloads.
    """

    def __init__(self, connection_string: str = "memory://") -> None:
        """Initialize the in-memory repository.

        Args:
            connection_string: Ignored for in-memory storage.
        """
        super().__init__(connection_string)
        self._events: list[StandardEvent] = []

    async def connect(self) -> None:
        """Establish connection (no-op for in-memory storage)."""
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection and clear all events."""
        self._events = []
        self._connected = False

    async def store(self, event: StandardEvent) -> bool:
        """Store a single event.

        Args:
            event: Event to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        self._events.append(event)
        return True

    async def store_bulk(self, events: list[StandardEvent]) -> int:
        """Store multiple events.

        Args:
            events: List of events to store.

        Returns:
            Number of events stored.

        Raises:
            StorageError: If not connected.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        if not events:
            return 0

        self._events.extend(events)
        return len(events)

    async def query(
        self,
        filter_: QueryFilter,
    ) -> list[StandardEvent]:
        """Query events with filters.

        Args:
            filter_: Query filter criteria.

        Returns:
            List of matching events.

        Raises:
            StorageError: If not connected.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        results = []

        for event in self._events:
            # Apply symbol filter
            if filter_.symbol:
                payload = event.payload
                if isinstance(payload, dict):
                    event_symbol = payload.get("symbol")
                else:
                    event_symbol = getattr(payload, "symbol", None)
                if event_symbol != filter_.symbol:
                    continue

            # Apply event_type filter
            if filter_.event_type and event.event_type != filter_.event_type:
                continue

            # Apply source filter
            if filter_.source and event.source != filter_.source:
                continue

            # Apply time range filters
            if filter_.start_time and event.timestamp < filter_.start_time:
                continue
            if filter_.end_time and event.timestamp > filter_.end_time:
                continue

            results.append(event)

        # Sort by timestamp descending
        results.sort(key=lambda e: e.timestamp, reverse=True)

        # Apply offset and limit
        start = filter_.offset
        end = start + filter_.limit
        return results[start:end]

    async def get_latest(
        self,
        symbol: Symbol,
        event_type: str,
        source: str | None = None,
    ) -> StandardEvent | None:
        """Get the most recent event for a symbol.

        Args:
            symbol: Trading symbol.
            event_type: Type of event.
            source: Optional source filter.

        Returns:
            Most recent event or None if not found.

        Raises:
            StorageError: If not connected.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        matching = []

        for event in self._events:
            # Check event type
            if event.event_type != event_type:
                continue

            # Check source
            if source and event.source != source:
                continue

            # Check symbol
            payload = event.payload
            if isinstance(payload, dict):
                event_symbol = payload.get("symbol")
            else:
                event_symbol = getattr(payload, "symbol", None)
            if event_symbol != symbol:
                continue

            matching.append(event)

        if not matching:
            return None

        # Return most recent (highest timestamp)
        return max(matching, key=lambda e: e.timestamp)

    async def aggregate_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Aggregate trade events into OHLCV candles.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe (e.g., "1m", "1h").
            start: Start time.
            end: End time.

        Returns:
            List of OHLCV data points.

        Raises:
            StorageError: If not connected.
            ValueError: If timeframe is not supported.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        # Parse timeframe
        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
        elif timeframe.endswith("h"):
            minutes = int(timeframe[:-1]) * 60
        elif timeframe.endswith("d"):
            minutes = int(timeframe[:-1]) * 60 * 24
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Filter trade events for the symbol and time range
        trades = []
        for event in self._events:
            if event.event_type != "trade":
                continue

            if event.timestamp < start or event.timestamp > end:
                continue

            payload = event.payload
            if isinstance(payload, dict):
                event_symbol = payload.get("symbol")
                price = payload.get("price")
                volume = payload.get("volume", 0.0)
            else:
                event_symbol = getattr(payload, "symbol", None)
                price = getattr(payload, "price", None)
                volume = getattr(payload, "volume", 0.0)

            if event_symbol != symbol:
                continue

            if price is not None:
                trades.append(
                    {
                        "timestamp": event.timestamp,
                        "price": price,
                        "volume": volume or 0.0,
                    }
                )

        if not trades:
            return []

        # Sort trades by timestamp
        trades.sort(key=lambda t: t["timestamp"])

        # Group trades into candles
        candles: dict[datetime, dict[str, Any]] = {}
        interval_ms = minutes * 60 * 1000

        for trade in trades:
            # Calculate candle timestamp by rounding down to interval
            trade_ts = trade["timestamp"]
            trade_ms = int(trade_ts.timestamp() * 1000)
            candle_ms = (trade_ms // interval_ms) * interval_ms
            candle_ts = datetime.fromtimestamp(candle_ms / 1000)

            if candle_ts not in candles:
                candles[candle_ts] = {
                    "timestamp": candle_ts,
                    "open": trade["price"],
                    "high": trade["price"],
                    "low": trade["price"],
                    "close": trade["price"],
                    "volume": trade["volume"],
                    "count": 1,
                }
            else:
                candle = candles[candle_ts]
                candle["high"] = max(candle["high"], trade["price"])
                candle["low"] = min(candle["low"], trade["price"])
                candle["close"] = trade["price"]
                candle["volume"] += trade["volume"]
                candle["count"] += 1

        # Sort candles by timestamp
        sorted_candles = sorted(candles.values(), key=lambda c: c["timestamp"])
        return sorted_candles

    async def get_latest_candle(
        self,
        symbol: str,
        interval: str,
    ) -> dict[str, Any] | None:
        """Get the latest candle for a symbol and interval.

        Args:
            symbol: Trading symbol.
            interval: Candle interval.

        Returns:
            Latest candle dict or None if not found.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        # Find matching candle events
        matching = []
        for event in self._events:
            if event.event_type != "ohlcv":
                continue

            payload = event.payload
            if isinstance(payload, dict):
                if payload.get("symbol") != symbol:
                    continue
                if payload.get("interval") != interval:
                    continue
                matching.append(event)

        if not matching:
            return None

        # Return most recent
        latest = max(matching, key=lambda e: e.timestamp)
        return {
            "t": latest.timestamp,
            "o": latest.payload.get("open", 0) if isinstance(latest.payload, dict) else 0,
            "h": latest.payload.get("high", 0) if isinstance(latest.payload, dict) else 0,
            "l": latest.payload.get("low", 0) if isinstance(latest.payload, dict) else 0,
            "c": latest.payload.get("close", 0) if isinstance(latest.payload, dict) else 0,
            "v": latest.payload.get("volume", 0) if isinstance(latest.payload, dict) else 0,
        }

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get historical candles for a symbol and interval.

        Args:
            symbol: Trading symbol.
            interval: Candle interval (e.g., "1m", "5m", "1h", "1d").
            start_time: Optional start time filter.
            end_time: Optional end time filter.
            limit: Maximum results.

        Returns:
            List of candle dictionaries.
        """
        if not self._connected:
            raise StorageError("Repository not connected")

        # Find matching candle events
        matching = []
        for event in self._events:
            if event.event_type != "ohlcv":
                continue

            payload = event.payload
            if isinstance(payload, dict):
                if payload.get("symbol") != symbol:
                    continue
                if payload.get("interval") != interval:
                    continue
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue
                matching.append(event)

        # Sort by timestamp descending, limit, then reverse for chronological order
        matching.sort(key=lambda e: e.timestamp, reverse=True)
        matching = matching[:limit]

        candles = []
        for event in reversed(matching):
            payload = event.payload
            if isinstance(payload, dict):
                candles.append({
                    "t": event.timestamp,
                    "o": payload.get("open", 0),
                    "h": payload.get("high", 0),
                    "l": payload.get("low", 0),
                    "c": payload.get("close", 0),
                    "v": payload.get("volume", 0),
                })

        return candles

    async def health_check(self) -> dict:
        """Check storage health.

        Returns:
            Health status dict.
        """
        return {
            "status": "healthy" if self._connected else "unhealthy",
            "latency_ms": 0.0,
            "document_count": len(self._events),
            "storage_size_mb": 0.0,
        }

    def clear(self) -> None:
        """Clear all events from memory.

        This is useful for testing to reset state between tests.
        """
        self._events = []

    # ============== Trader Query Methods ==============

    async def get_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get tracked traders (stub for testing).

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only return active traders.
            limit: Maximum results.

        Returns:
            Empty list (stub implementation).
        """
        return []

    async def count_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
    ) -> int:
        """Count tracked traders (stub for testing).

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only count active traders.

        Returns:
            0 (stub implementation).
        """
        return 0

    async def get_trader_by_address(self, address: str) -> dict[str, Any] | None:
        """Get a trader by address (stub for testing).

        Args:
            address: Trader Ethereum address.

        Returns:
            None (stub implementation).
        """
        return None

    async def get_trader_current_state(self, address: str) -> dict[str, Any] | None:
        """Get a trader's current state (stub for testing).

        Args:
            address: Trader Ethereum address.

        Returns:
            None (stub implementation).
        """
        return None

    async def get_trader_positions_history(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get position history for a trader (stub for testing).

        Args:
            address: Trader Ethereum address.
            start_time: Start time for history.
            limit: Maximum results.

        Returns:
            Empty list (stub implementation).
        """
        return []

    async def get_trader_signals(
        self,
        address: str,
        start_time: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get signals for a specific trader (stub for testing).

        Args:
            address: Trader Ethereum address.
            start_time: Start time for signals.
            limit: Maximum results.

        Returns:
            Empty list (stub implementation).
        """
        return []

    # ============== Signal Query Methods ==============

    async def get_signals(
        self,
        symbol: str,
        start_time: datetime | None = None,
        recommendation: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get trading signals for a symbol (stub for testing).

        Args:
            symbol: Trading symbol.
            start_time: Optional start time filter.
            recommendation: Filter by recommendation.
            limit: Maximum results.

        Returns:
            Empty list (stub implementation).
        """
        return []

    async def get_current_signal(self, symbol: str) -> dict[str, Any] | None:
        """Get the current/latest signal for a symbol (stub for testing).

        Args:
            symbol: Trading symbol.

        Returns:
            None (stub implementation).
        """
        return None

    async def get_signal_stats(
        self,
        symbol: str,
        start_time: datetime,
    ) -> dict[str, Any]:
        """Get aggregated signal statistics (stub for testing).

        Args:
            symbol: Trading symbol.
            start_time: Start time for statistics.

        Returns:
            Empty stats (stub implementation).
        """
        return {
            "total": 0,
            "buy": 0,
            "sell": 0,
            "neutral": 0,
            "avg_confidence": 0.0,
            "avg_long_bias": 0.0,
        }

    # ============== Trader Management Methods ==============

    async def track_trader(
        self,
        address: str,
        name: str | None = None,
        score: float = 0,
        tags: list[str] | None = None,
    ) -> bool:
        """Add or update a tracked trader (stub for testing).

        Args:
            address: Trader Ethereum address.
            name: Optional display name.
            score: Initial score.
            tags: Optional tags.

        Returns:
            True (stub implementation).
        """
        return True

    async def untrack_trader(self, address: str) -> bool:
        """Mark a trader as inactive (stub for testing).

        Args:
            address: Trader Ethereum address.

        Returns:
            True (stub implementation).
        """
        return True
