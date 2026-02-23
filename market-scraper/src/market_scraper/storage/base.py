"""Base storage module for the Market Scraper Framework."""

from abc import ABC, abstractmethod
from datetime import datetime
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
