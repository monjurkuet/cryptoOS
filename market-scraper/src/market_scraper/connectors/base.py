# src/market_scraper/connectors/base.py

"""Base classes for market data connectors."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe


class ConnectorConfig(BaseModel):
    """Base configuration for all connectors."""

    name: str = Field(..., description="Unique connector identifier")
    enabled: bool = Field(default=True, description="Whether connector is enabled")
    rate_limit_per_second: float = Field(
        default=10.0, description="Rate limit for API requests per second"
    )
    timeout_seconds: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries in seconds")


class DataConnector(ABC):
    """Abstract base class for all market data connectors.

    Implementations must provide:
    - Connection lifecycle management
    - Historical data fetching
    - Real-time streaming (optional)
    - Health checking
    """

    def __init__(self, config: ConnectorConfig) -> None:
        """Initialize the connector with configuration.

        Args:
            config: Connector configuration
        """
        self._config = config
        self._connected = False
        self._last_heartbeat: datetime | None = None

    @property
    def name(self) -> str:
        """Unique connector identifier."""
        return self._config.name

    @property
    def is_connected(self) -> bool:
        """Connection state."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to data source.

        Raises:
            ConnectionError: If connection fails after retries
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connection."""
        pass

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical market data.

        Args:
            symbol: Trading pair/symbol
            timeframe: Data granularity (e.g., "1m", "1h", "1d")
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized market data events

        Raises:
            DataFetchError: If fetch fails
            ValidationError: If response parsing fails
        """
        pass

    @abstractmethod
    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time market data.

        Args:
            symbols: List of symbols to subscribe to

        Yields:
            Standardized market data events as they arrive

        Raises:
            ConnectionError: If stream connection fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
        """
        pass

    async def __aenter__(self) -> "DataConnector":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: object | None,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()
