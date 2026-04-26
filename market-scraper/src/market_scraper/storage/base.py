"""Base storage module for the Market Scraper Framework."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
import hashlib
from typing import Any

from pydantic import BaseModel, Field

from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe


class QueryFilter(BaseModel):
    """Filter criteria for data queries."""

    symbol: Symbol | None = Field(
        default=None,
        description="Trading pair/symbol to filter by",
    )
    event_type: str | None = Field(
        default=None,
        description="Event type to filter by",
    )
    start_time: datetime | None = Field(
        default=None,
        description="Start of time range (inclusive)",
    )
    end_time: datetime | None = Field(
        default=None,
        description="End of time range (inclusive)",
    )
    source: str | None = Field(
        default=None,
        description="Event source to filter by",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of results to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of results to skip",
    )


class DataRepository(ABC):
    """Abstract base class for data storage implementations.

    Provides unified interface for:
    - Event storage and retrieval
    - Aggregation queries
    - Time-series data management
    """

    def __init__(self, connection_string: str) -> None:
        """Initialize the repository.

        Args:
            connection_string: Connection string for the storage backend.
        """
        self._connection_string = connection_string
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if repository is connected to storage backend.

        Returns:
            True if connected, False otherwise.
        """
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to storage backend.

        Raises:
            StorageError: If connection fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to storage backend."""
        pass

    @abstractmethod
    async def store(self, event: StandardEvent) -> bool:
        """Store a single event.

        Args:
            event: Event to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If storage operation fails.
        """
        pass

    @abstractmethod
    async def store_bulk(self, events: list[StandardEvent]) -> int:
        """Store multiple events efficiently.

        Args:
            events: List of events to store.

        Returns:
            Number of events stored.

        Raises:
            StorageError: If storage operation fails.
        """
        pass

    @abstractmethod
    async def query(
        self,
        filter_: QueryFilter,
    ) -> list[StandardEvent]:
        """Query stored events.

        Args:
            filter_: Query filter criteria.

        Returns:
            List of matching events.

        Raises:
            StorageError: If query operation fails.
        """
        pass

    @abstractmethod
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
            StorageError: If query operation fails.
        """
        pass

    @abstractmethod
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
            List of OHLCV data points with keys:
            - timestamp: datetime
            - open: float
            - high: float
            - low: float
            - close: float
            - volume: float
            - count: int

        Raises:
            StorageError: If aggregation fails.
            ValueError: If timeframe is not supported.
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check storage health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time in milliseconds
            - Additional backend-specific metrics
        """
        pass

    # ============== Candle Query Methods ==============

    @abstractmethod
    async def store_candle(self, candle: Any, symbol: str, interval: str) -> bool:
        """Store a candle in the canonical candle collection.

        Args:
            candle: Candle snapshot to store.
            symbol: Trading symbol.
            interval: Candle interval.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def get_latest_candle(
        self,
        symbol: str,
        interval: str,
    ) -> dict[str, Any] | None:
        """Get the latest candle for a symbol and interval.

        Args:
            symbol: Trading symbol.
            interval: Candle interval (e.g., "1m", "5m", "1h", "1d").

        Returns:
            Latest candle dictionary with keys:
            - t: timestamp
            - o: open price
            - h: high price
            - l: low price
            - c: close price
            - v: volume

            Or None if not found.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
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
            limit: Maximum results (default 100, max 10000).

        Returns:
            List of candle dictionaries, each with:
            - t: timestamp
            - o: open price
            - h: high price
            - l: low price
            - c: close price
            - v: volume

        Raises:
            StorageError: If query fails.
        """
        pass

    async def __aenter__(self) -> "DataRepository":
        """Async context manager entry.

        Returns:
            Self after connecting.
        """
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Async context manager exit.

        Args:
            exc_type: Exception type if an error occurred.
            exc_val: Exception value if an error occurred.
            exc_tb: Exception traceback if an error occurred.
        """
        await self.disconnect()

    # ============== Shared Trader State Helpers ==============

    @staticmethod
    def _normalize_address(address: str) -> str:
        """Normalize an Ethereum address for storage and lookups."""
        return str(address or "").lower()

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Convert arbitrary values to float safely."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime | None:
        """Normalize datetime-like values to UTC-aware datetimes."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return None

    @classmethod
    def _extract_live_position_snapshot(
        cls,
        positions: Any,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Extract a normalized configured-symbol position from current-state payloads."""
        if not isinstance(positions, list):
            return None

        normalized_symbol = str(symbol or "").upper()
        for row in positions:
            if not isinstance(row, dict):
                continue
            position = row.get("position", row)
            if not isinstance(position, dict):
                continue
            if str(position.get("coin", "")).upper() != normalized_symbol:
                continue

            size = cls._safe_float(position.get("szi", 0) or 0)
            direction = "long" if size > 0 else "short" if size < 0 else None
            return {
                "coin": normalized_symbol,
                "size": size,
                "abs_size": abs(size),
                "direction": direction,
                "entry_price": cls._safe_float(position.get("entryPx", 0) or 0),
                "mark_price": cls._safe_float(position.get("markPx", 0) or 0),
                "unrealized_pnl": cls._safe_float(position.get("unrealizedPnl", 0) or 0),
            }

        return None

    @classmethod
    def _extract_history_position_snapshot(
        cls,
        position: Any,
        symbol: str,
    ) -> dict[str, Any] | None:
        """Extract a normalized configured-symbol position from history rows."""
        if not isinstance(position, dict):
            return None
        if str(position.get("coin", "")).upper() != str(symbol or "").upper():
            return None

        size = cls._safe_float(position.get("sz", 0) or 0)
        direction = "long" if size > 0 else "short" if size < 0 else None
        return {
            "coin": str(symbol or "").upper(),
            "size": size,
            "abs_size": abs(size),
            "direction": direction,
            "entry_price": cls._safe_float(position.get("ep", 0) or 0),
            "mark_price": cls._safe_float(position.get("mp", 0) or 0),
            "unrealized_pnl": cls._safe_float(position.get("upnl", 0) or 0),
        }

    @classmethod
    def _build_trade_id(
        cls,
        address: str,
        symbol: str,
        direction: str,
        opened_at: datetime,
        closed_at: datetime,
        close_reason: str,
    ) -> str:
        """Build deterministic closed-trade IDs for idempotent writes."""
        payload = "|".join(
            [
                cls._normalize_address(address),
                str(symbol or "").upper(),
                direction,
                cls._normalize_datetime(opened_at).isoformat(),
                cls._normalize_datetime(closed_at).isoformat(),
                close_reason,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def _build_closed_trade(
        cls,
        address: str,
        symbol: str,
        previous_position: dict[str, Any],
        previous_meta: dict[str, Any] | None,
        previous_last_event_time: datetime | None,
        closed_at: datetime,
        close_reason: str,
    ) -> dict[str, Any] | None:
        """Build a normalized immutable closed-trade row from two live snapshots."""
        direction = str((previous_meta or {}).get("direction") or previous_position.get("direction") or "")
        if direction not in {"long", "short"}:
            return None

        opened_at = (
            cls._normalize_datetime((previous_meta or {}).get("opened_at"))
            or cls._normalize_datetime(previous_last_event_time)
            or cls._normalize_datetime(closed_at)
        )
        closed_at_utc = cls._normalize_datetime(closed_at) or opened_at
        entry_price = cls._safe_float(
            (previous_meta or {}).get("entry_price"),
            cls._safe_float(previous_position.get("entry_price"), 0.0),
        )
        previous_abs_size = cls._safe_float(previous_position.get("abs_size"), 0.0)
        max_abs_size = max(
            cls._safe_float((previous_meta or {}).get("max_abs_size"), previous_abs_size),
            previous_abs_size,
        )

        trade_id = cls._build_trade_id(
            address=address,
            symbol=symbol,
            direction=direction,
            opened_at=opened_at,
            closed_at=closed_at_utc,
            close_reason=close_reason,
        )

        return {
            "trade_id": trade_id,
            "eth": cls._normalize_address(address),
            "symbol": str(symbol or "").upper(),
            "dir": direction,
            "opened_at": opened_at,
            "closed_at": closed_at_utc,
            "entry_price": entry_price,
            "close_reference_price": cls._safe_float(previous_position.get("mark_price"), 0.0),
            "max_abs_size": max_abs_size,
            "final_abs_size": previous_abs_size,
            "last_unrealized_pnl": cls._safe_float(previous_position.get("unrealized_pnl"), 0.0),
            "close_reason": close_reason,
            "t": closed_at_utc,
        }

    @classmethod
    def build_trader_current_state_payload(
        cls,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
        existing_state: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Build live current-state payload and optional closed-trade row."""
        previous_position = cls._extract_live_position_snapshot(
            (existing_state or {}).get("positions", []),
            symbol,
        )
        previous_meta = dict((existing_state or {}).get("btc_trade_meta") or {})
        previous_last_event_time_raw = (existing_state or {}).get("last_event_time")
        previous_last_event_time = cls._normalize_datetime(previous_last_event_time_raw)
        current_position = cls._extract_live_position_snapshot(positions, symbol)

        closed_trade: dict[str, Any] | None = None
        if previous_position and previous_position.get("direction") in {"long", "short"}:
            current_direction = (current_position or {}).get("direction")
            previous_direction = previous_position.get("direction")
            if current_direction is None:
                closed_trade = cls._build_closed_trade(
                    address=address,
                    symbol=symbol,
                    previous_position=previous_position,
                    previous_meta=previous_meta,
                    previous_last_event_time=previous_last_event_time,
                    closed_at=event_timestamp,
                    close_reason="flat",
                )
            elif current_direction != previous_direction:
                closed_trade = cls._build_closed_trade(
                    address=address,
                    symbol=symbol,
                    previous_position=previous_position,
                    previous_meta=previous_meta,
                    previous_last_event_time=previous_last_event_time,
                    closed_at=event_timestamp,
                    close_reason="flip",
                )

        next_trade_meta: dict[str, Any] = {}
        if current_position and current_position.get("direction") in {"long", "short"}:
            current_direction = str(current_position["direction"])
            previous_direction = str(previous_position.get("direction")) if previous_position else None
            if previous_direction != current_direction:
                next_trade_meta = {
                    "opened_at": event_timestamp,
                    "entry_price": cls._safe_float(current_position.get("entry_price"), 0.0),
                    "direction": current_direction,
                    "max_abs_size": cls._safe_float(current_position.get("abs_size"), 0.0),
                }
            else:
                next_trade_meta = {
                    "opened_at": previous_meta.get("opened_at")
                    or previous_last_event_time_raw
                    or event_timestamp,
                    "entry_price": cls._safe_float(
                        previous_meta.get("entry_price"),
                        cls._safe_float(current_position.get("entry_price"), 0.0),
                    ),
                    "direction": current_direction,
                    "max_abs_size": max(
                        cls._safe_float(
                            previous_meta.get("max_abs_size"),
                            cls._safe_float(previous_position.get("abs_size"), 0.0)
                            if previous_position
                            else 0.0,
                        ),
                        cls._safe_float(current_position.get("abs_size"), 0.0),
                    ),
                }

        payload = {
            "eth": cls._normalize_address(address),
            "symbol": str(symbol or "").upper(),
            "positions": positions,
            "open_orders": open_orders,
            "margin_summary": dict(margin_summary or {}),
            "last_event_time": event_timestamp,
            "source": source,
            "btc_trade_meta": next_trade_meta,
        }
        return payload, closed_trade

    @classmethod
    def derive_closed_trades_from_position_history(
        cls,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        current_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Best-effort backfill of closed trades from stored BTC position snapshots."""
        symbol_key = str(symbol or "").upper()
        deduped_rows: list[dict[str, Any]] = []
        last_signature: tuple[Any, ...] | None = None

        for row in sorted(
            (position for position in positions if isinstance(position, dict)),
            key=lambda position: cls._normalize_datetime(position.get("t")) or datetime.min.replace(tzinfo=UTC),
        ):
            snapshot = cls._extract_history_position_snapshot(row, symbol_key)
            if not snapshot or snapshot.get("direction") not in {"long", "short"}:
                continue

            signature = (
                snapshot.get("direction"),
                snapshot.get("size"),
                snapshot.get("entry_price"),
                snapshot.get("mark_price"),
                snapshot.get("unrealized_pnl"),
            )
            if signature == last_signature:
                continue
            deduped_rows.append(row)
            last_signature = signature

        closed_trades: list[dict[str, Any]] = []
        open_position: dict[str, Any] | None = None
        open_meta: dict[str, Any] | None = None
        last_event_time: datetime | None = None

        for row in deduped_rows:
            snapshot = cls._extract_history_position_snapshot(row, symbol_key)
            row_time = cls._normalize_datetime(row.get("t"))
            if not snapshot or not row_time:
                continue

            if open_position is None:
                open_position = snapshot
                open_meta = {
                    "opened_at": row_time,
                    "entry_price": cls._safe_float(snapshot.get("entry_price"), 0.0),
                    "direction": snapshot.get("direction"),
                    "max_abs_size": cls._safe_float(snapshot.get("abs_size"), 0.0),
                }
                last_event_time = row_time
                continue

            if open_position.get("direction") == snapshot.get("direction"):
                open_meta = {
                    "opened_at": (open_meta or {}).get("opened_at", row_time),
                    "entry_price": cls._safe_float(
                        (open_meta or {}).get("entry_price"),
                        cls._safe_float(snapshot.get("entry_price"), 0.0),
                    ),
                    "direction": snapshot.get("direction"),
                    "max_abs_size": max(
                        cls._safe_float(
                            (open_meta or {}).get("max_abs_size"),
                            cls._safe_float(open_position.get("abs_size"), 0.0),
                        ),
                        cls._safe_float(snapshot.get("abs_size"), 0.0),
                    ),
                }
                open_position = snapshot
                last_event_time = row_time
                continue

            closed_trade = cls._build_closed_trade(
                address=address,
                symbol=symbol_key,
                previous_position=open_position,
                previous_meta=open_meta,
                previous_last_event_time=last_event_time,
                closed_at=row_time,
                close_reason="flip",
            )
            if closed_trade:
                closed_trades.append(closed_trade)

            open_position = snapshot
            open_meta = {
                "opened_at": row_time,
                "entry_price": cls._safe_float(snapshot.get("entry_price"), 0.0),
                "direction": snapshot.get("direction"),
                "max_abs_size": cls._safe_float(snapshot.get("abs_size"), 0.0),
            }
            last_event_time = row_time

        if open_position and current_state:
            current_position = cls._extract_live_position_snapshot(current_state.get("positions", []), symbol_key)
            current_direction = (current_position or {}).get("direction")
            if current_direction is None:
                closed_trade = cls._build_closed_trade(
                    address=address,
                    symbol=symbol_key,
                    previous_position=open_position,
                    previous_meta=open_meta,
                    previous_last_event_time=last_event_time,
                    closed_at=current_state.get("last_event_time") or current_state.get("updated_at") or last_event_time,
                    close_reason="flat",
                )
                if closed_trade:
                    closed_trades.append(closed_trade)

        return closed_trades

    # ============== Trader Query Methods ==============

    @abstractmethod
    async def get_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get tracked traders.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only return active traders.
            limit: Maximum results.

        Returns:
            List of trader dictionaries.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def count_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
    ) -> int:
        """Count tracked traders.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only count active traders.

        Returns:
            Number of matching traders.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_by_address(self, address: str) -> dict[str, Any] | None:
        """Get a trader by address.

        Args:
            address: Trader Ethereum address.

        Returns:
            Trader dictionary or None if not found.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_current_state(self, address: str) -> dict[str, Any] | None:
        """Get a trader's current state including positions.

        Args:
            address: Trader Ethereum address.

        Returns:
            Current state dictionary with positions, or None.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_current_states(
        self,
        addresses: list[str],
        symbol: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get current state snapshots for multiple traders.

        Args:
            addresses: Trader Ethereum addresses.
            symbol: Optional symbol filter.

        Returns:
            Mapping of normalized address -> current-state dictionary.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_positions_history(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get position history for a trader.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for history.
            limit: Maximum results.

        Returns:
            List of position dictionaries.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_closed_trades(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get closed trades for a trader.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for history.
            limit: Maximum results.

        Returns:
            List of closed-trade dictionaries ordered by close time descending.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_trader_signals(
        self,
        address: str,
        start_time: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get signals for a specific trader.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for signals.
            limit: Maximum results.

        Returns:
            List of signal dictionaries.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def store_leaderboard_snapshot(
        self,
        symbol: str,
        total_count: int,
        tracked_count: int,
        timestamp: datetime | None = None,
    ) -> bool:
        """Store a lightweight leaderboard snapshot.

        Args:
            symbol: Trading symbol.
            total_count: Total traders seen in leaderboard.
            tracked_count: Traders selected for tracking.
            timestamp: Snapshot time (defaults to now if omitted).

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def upsert_tracked_trader_data(
        self,
        trader: dict[str, Any],
        updated_at: datetime | None = None,
    ) -> bool:
        """Upsert tracked trader data from leaderboard selection.

        Args:
            trader: Trader dictionary containing normalized tracking fields.
            updated_at: Update timestamp (defaults to now if omitted).

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def deactivate_unselected_traders(
        self,
        selected_addresses: list[str],
        updated_at: datetime | None = None,
    ) -> int:
        """Deactivate tracked traders that are not currently selected.

        Args:
            selected_addresses: Addresses that should remain active.
            updated_at: Update timestamp (defaults to now if omitted).

        Returns:
            Number of modified documents.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def get_active_trader_addresses(self, limit: int = 5000) -> list[str]:
        """Get active tracked trader addresses.

        Args:
            limit: Maximum addresses to return.

        Returns:
            List of Ethereum addresses.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def upsert_trader_current_state(
        self,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
    ) -> bool:
        """Upsert the latest trader current state snapshot.

        Args:
            address: Trader Ethereum address.
            symbol: Trading symbol.
            positions: Latest position payload list.
            open_orders: Latest open orders payload list.
            margin_summary: Latest margin summary payload.
            event_timestamp: Event time.
            source: Event source identifier.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def store_trader_position(self, position: Any) -> bool:
        """Store a normalized trader position history row.

        Args:
            position: Position snapshot to store.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def store_trader_closed_trade(self, trade: Any) -> bool:
        """Store an immutable closed-trade row.

        Args:
            trade: Closed-trade payload or model.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def store_trader_score(self, score: Any) -> bool:
        """Store a trader score history row.

        Args:
            score: Score snapshot to store.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    # ============== Signal Query Methods ==============

    @abstractmethod
    async def get_signals(
        self,
        symbol: str,
        start_time: datetime | None = None,
        recommendation: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get trading signals for a symbol.

        Args:
            symbol: Trading symbol.
            start_time: Optional start time filter.
            recommendation: Filter by recommendation (BUY, SELL, NEUTRAL).
            limit: Maximum results.

        Returns:
            List of signal dictionaries.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_current_signal(self, symbol: str) -> dict[str, Any] | None:
        """Get the current/latest signal for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Latest signal dictionary or None.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
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
            Statistics dictionary with counts and averages.

        Raises:
            StorageError: If query fails.
        """
        pass

    @abstractmethod
    async def get_signal_by_id(self, signal_id: str) -> dict[str, Any] | None:
        """Get a signal by its ID.

        Args:
            signal_id: Signal ObjectId as string.

        Returns:
            Signal dictionary or None if not found.

        Raises:
            StorageError: If query fails.
        """
        pass

    # ============== Trader Management Methods ==============

    @abstractmethod
    async def track_trader(
        self,
        address: str,
        name: str | None = None,
        score: float = 0,
        tags: list[str] | None = None,
    ) -> bool:
        """Add or update a tracked trader.

        Args:
            address: Trader Ethereum address.
            name: Optional display name.
            score: Initial score.
            tags: Optional tags.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass

    @abstractmethod
    async def untrack_trader(self, address: str) -> bool:
        """Mark a trader as inactive (soft delete).

        Args:
            address: Trader Ethereum address.

        Returns:
            True if successful.

        Raises:
            StorageError: If operation fails.
        """
        pass
