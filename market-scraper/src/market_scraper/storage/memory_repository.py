"""In-memory repository implementation for testing."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.core.types import Symbol, Timeframe
from market_scraper.storage.base import DataRepository, QueryFilter
from market_scraper.storage.models import Candle


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
        self._leaderboard_history: list[dict[str, Any]] = []
        self._tracked_traders: dict[str, dict[str, Any]] = {}
        self._trader_current_state: dict[tuple[str, str], dict[str, Any]] = {}
        self._trader_positions_history: list[dict[str, Any]] = []
        self._trader_scores_history: list[dict[str, Any]] = []
        self._candles: dict[tuple[str, str], dict[datetime, dict[str, Any]]] = {}
        self._signals: list[dict[str, Any]] = []

    @staticmethod
    def _normalize_tags(tags: Any) -> list[str]:
        """Normalize tag collections for stable equality checks."""
        return sorted(str(tag) for tag in (tags or []))

    @staticmethod
    def _position_snapshot_payload(position: dict[str, Any]) -> dict[str, Any]:
        """Build comparable payload for position history rows."""
        return {
            "eth": str(position.get("eth", "")).lower(),
            "coin": str(position.get("coin", "")),
            "sz": float(position.get("sz", 0) or 0),
            "ep": float(position.get("ep", 0) or 0),
            "mp": float(position.get("mp", 0) or 0),
            "upnl": float(position.get("upnl", 0) or 0),
            "lev": float(position.get("lev", 0) or 0),
            "liq": position.get("liq"),
        }

    @staticmethod
    def _score_snapshot_payload(score: dict[str, Any]) -> dict[str, Any]:
        """Build comparable payload for trader score history rows."""
        return {
            "eth": str(score.get("eth", "")).lower(),
            "score": float(score.get("score", 0) or 0),
            "tags": MemoryRepository._normalize_tags(score.get("tags")),
            "acct_val": float(score.get("acct_val", 0) or 0),
            "all_roi": float(score.get("all_roi", 0) or 0),
            "month_roi": float(score.get("month_roi", 0) or 0),
            "week_roi": float(score.get("week_roi", 0) or 0),
        }

    async def connect(self) -> None:
        """Establish connection (no-op for in-memory storage)."""
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection and clear all events."""
        self._events = []
        self._leaderboard_history = []
        self._tracked_traders = {}
        self._trader_current_state = {}
        self._trader_positions_history = []
        self._trader_scores_history = []
        self._candles = {}
        self._signals = []
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

    async def store_candle(self, candle: Candle, symbol: str, interval: str) -> bool:
        """Store a candle in canonical in-memory candle storage."""
        if not self._connected:
            raise StorageError("Repository not connected")

        key = (symbol, interval)
        if key not in self._candles:
            self._candles[key] = {}

        self._candles[key][candle.t] = candle.model_dump()
        return True

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

        candles = self._candles.get((symbol, interval), {})
        if not candles:
            return None

        latest_timestamp = max(candles)
        return dict(candles[latest_timestamp])

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

        matching = []
        for timestamp, candle in self._candles.get((symbol, interval), {}).items():
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            matching.append(candle)

        matching.sort(key=lambda candle: candle["t"], reverse=True)
        matching = matching[:limit]
        return list(reversed([dict(candle) for candle in matching]))

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
        self._leaderboard_history = []
        self._tracked_traders = {}
        self._trader_current_state = {}
        self._trader_positions_history = []
        self._trader_scores_history = []
        self._candles = {}

    # ============== Trader Query Methods ==============

    async def get_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get tracked traders from in-memory state.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only return active traders.
            limit: Maximum results.

        Returns:
            Filtered tracked trader dictionaries sorted by score descending.
        """
        traders = list(self._tracked_traders.values())

        if active_only:
            traders = [t for t in traders if t.get("active", True)]

        traders = [t for t in traders if float(t.get("score", 0) or 0) >= min_score]

        if tag:
            traders = [t for t in traders if tag in t.get("tags", [])]

        traders.sort(key=lambda t: float(t.get("score", 0) or 0), reverse=True)
        return traders[:limit]

    async def count_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
    ) -> int:
        """Count tracked traders from in-memory state.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only count active traders.

        Returns:
            Number of matching tracked traders.
        """
        traders = list(self._tracked_traders.values())

        if active_only:
            traders = [t for t in traders if t.get("active", True)]

        traders = [t for t in traders if float(t.get("score", 0) or 0) >= min_score]

        if tag:
            traders = [t for t in traders if tag in t.get("tags", [])]

        return len(traders)

    async def get_trader_by_address(self, address: str) -> dict[str, Any] | None:
        """Get a trader by address from in-memory state.

        Args:
            address: Trader Ethereum address.

        Returns:
            Trader dictionary or None.
        """
        return self._tracked_traders.get(address.lower())

    async def get_trader_current_state(self, address: str) -> dict[str, Any] | None:
        """Get a trader's current state from in-memory state.

        Args:
            address: Trader Ethereum address.

        Returns:
            Current-state dictionary or None.
        """
        normalized = address.lower()
        for (eth, _symbol), state in self._trader_current_state.items():
            if eth == normalized:
                return state
        return None

    async def get_trader_positions_history(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get position history for a trader from in-memory state.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for history.
            limit: Maximum results.

        Returns:
            Position history ordered by time descending.
        """
        normalized = address.lower()
        rows = [
            p
            for p in self._trader_positions_history
            if p.get("eth") == normalized
            and isinstance(p.get("t"), datetime)
            and p["t"] >= start_time
        ]
        rows.sort(key=lambda p: p.get("t", datetime.min), reverse=True)
        return rows[:limit]

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

    async def store_leaderboard_snapshot(
        self,
        symbol: str,
        total_count: int,
        tracked_count: int,
        timestamp: datetime | None = None,
    ) -> bool:
        """Store a lightweight leaderboard snapshot (in-memory)."""
        self._leaderboard_history.append(
            {
                "t": timestamp or datetime.now(),
                "symbol": symbol,
                "traderCount": total_count,
                "trackedCount": tracked_count,
            }
        )
        return True

    async def upsert_tracked_trader_data(
        self,
        trader: dict[str, Any],
        updated_at: datetime | None = None,
    ) -> bool:
        """Upsert tracked trader data (in-memory)."""
        address = str(trader.get("eth", "")).lower()
        if not address:
            return False

        now = updated_at or datetime.now()
        existing = self._tracked_traders.get(address, {})
        added_at = existing.get("added_at", now)
        normalized_doc = {
            "eth": address,
            "name": trader.get("name"),
            "score": float(trader.get("score", 0)),
            "acct_val": float(trader.get("acct_val", 0)),
            "tags": self._normalize_tags(trader.get("tags")),
            "performances": dict(trader.get("performances") or {}),
            "active": bool(trader.get("active", True)),
        }

        if existing and all(existing.get(key) == value for key, value in normalized_doc.items()):
            return True

        self._tracked_traders[address] = {
            **existing,
            **normalized_doc,
            "updated_at": now,
            "added_at": added_at,
        }
        return True

    async def deactivate_unselected_traders(
        self,
        selected_addresses: list[str],
        updated_at: datetime | None = None,
    ) -> int:
        """Deactivate unselected tracked traders (in-memory)."""
        selected = {a.lower() for a in selected_addresses}
        now = updated_at or datetime.now()
        modified = 0

        for address, trader in self._tracked_traders.items():
            if address in selected:
                continue
            if trader.get("active", True):
                trader["active"] = False
                trader["updated_at"] = now
                modified += 1

        return modified

    async def get_active_trader_addresses(self, limit: int = 5000) -> list[str]:
        """Get active trader addresses (in-memory)."""
        addresses = [a for a, d in self._tracked_traders.items() if d.get("active", True)]
        return addresses[:limit]

    async def upsert_trader_current_state(
        self,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
    ) -> bool:
        """Upsert trader current state (in-memory)."""
        normalized = address.lower()
        state_key = (normalized, symbol)
        payload = {
            "eth": normalized,
            "symbol": symbol,
            "positions": positions,
            "margin_summary": margin_summary or {},
            "last_event_time": event_timestamp,
            "source": source,
        }

        existing = self._trader_current_state.get(state_key)
        if existing and all(existing.get(key) == value for key, value in payload.items()):
            return True

        payload["updated_at"] = datetime.now()
        self._trader_current_state[state_key] = payload
        return True

    async def store_trader_position(self, position: Any) -> bool:
        """Store a normalized trader position history row (in-memory)."""
        data = position.model_dump() if hasattr(position, "model_dump") else dict(position)
        data["eth"] = str(data.get("eth", "")).lower()
        comparable = self._position_snapshot_payload(data)
        for latest in reversed(self._trader_positions_history):
            latest_payload = self._position_snapshot_payload(latest)
            if (
                latest_payload["eth"] == comparable["eth"]
                and latest_payload["coin"] == comparable["coin"]
            ):
                if latest_payload == comparable:
                    return True
                break
        self._trader_positions_history.append(data)
        return True

    async def store_trader_score(self, score: Any) -> bool:
        """Store a trader score history row (in-memory)."""
        data = score.model_dump() if hasattr(score, "model_dump") else dict(score)
        data["eth"] = str(data.get("eth", "")).lower()
        data["tags"] = self._normalize_tags(data.get("tags"))
        comparable = self._score_snapshot_payload(data)
        for latest in reversed(self._trader_scores_history):
            latest_payload = self._score_snapshot_payload(latest)
            if latest_payload["eth"] == comparable["eth"]:
                if latest_payload == comparable:
                    return True
                break
        self._trader_scores_history.append(data)
        return True

    async def store_signal(self, signal: Any) -> bool:
        """Store a trading signal row (in-memory)."""
        data = signal.model_dump() if hasattr(signal, "model_dump") else dict(signal)
        self._signals.append(data)
        return True

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
        """Get the current/latest signal for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Latest signal row or None.
        """
        matching = [s for s in self._signals if s.get("symbol") == symbol]
        if not matching:
            return None
        return max(matching, key=lambda s: s.get("t", datetime.min))

    async def get_signal_stats(
        self,
        symbol: str,
        start_time: datetime,
    ) -> dict[str, Any]:
        """Get aggregated signal statistics.

        Args:
            symbol: Trading symbol.
            start_time: Start time for statistics.

        Returns:
            Aggregated signal statistics.
        """
        matching = [
            s
            for s in self._signals
            if s.get("symbol") == symbol
            and isinstance(s.get("t"), datetime)
            and s["t"] >= start_time
        ]
        if not matching:
            return {
                "total": 0,
                "buy": 0,
                "sell": 0,
                "neutral": 0,
                "avg_confidence": 0.0,
                "avg_long_bias": 0.0,
            }

        total = len(matching)
        buy = sum(1 for s in matching if s.get("rec") == "BUY")
        sell = sum(1 for s in matching if s.get("rec") == "SELL")
        neutral = sum(1 for s in matching if s.get("rec") == "NEUTRAL")
        avg_confidence = sum(float(s.get("conf", 0) or 0) for s in matching) / total
        avg_long_bias = sum(float(s.get("long_bias", 0) or 0) for s in matching) / total

        return {
            "total": total,
            "buy": buy,
            "sell": sell,
            "neutral": neutral,
            "avg_confidence": round(avg_confidence, 4),
            "avg_long_bias": round(avg_long_bias, 4),
        }

    async def get_signal_by_id(self, signal_id: str) -> dict[str, Any] | None:
        """Get a signal by its ID (stub for testing).

        Args:
            signal_id: Signal ObjectId as string.

        Returns:
            None (stub implementation).
        """
        return None

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
