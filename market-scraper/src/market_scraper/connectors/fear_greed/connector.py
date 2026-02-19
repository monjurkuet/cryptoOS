# src/market_scraper/connectors/fear_greed/connector.py

"""Fear & Greed Index connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.fear_greed.client import FearGreedClient
from market_scraper.connectors.fear_greed.config import FearGreedConfig
from market_scraper.connectors.fear_greed.parsers import (
    parse_fear_greed_historical,
    parse_fear_greed_response,
    parse_fear_greed_summary,
    validate_fear_greed_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class FearGreedConnector(DataConnector):
    """Connector for Fear & Greed Index data.

    Provides access to the Alternative.me Fear & Greed Index, a sentiment
    indicator for the cryptocurrency market ranging from 0 (Extreme Fear)
    to 100 (Extreme Greed).

    The index is updated daily and provides historical data for analysis.

    Attributes:
        config: Fear & Greed-specific configuration
        client: HTTP client for API interactions
    """

    def __init__(self, config: FearGreedConfig) -> None:
        """Initialize the Fear & Greed connector.

        Args:
            config: Fear & Greed connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = FearGreedClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Fear & Greed API.

        Initializes the HTTP client and verifies connectivity.

        Raises:
            ConnectionError: If connection fails after retries
        """
        try:
            await self._client.connect()
            self._connected = True
            logger.info("fear_greed_connector_connected")
        except Exception as e:
            logger.error("fear_greed_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Fear & Greed API: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to Fear & Greed API.

        Closes HTTP sessions and releases resources.
        """
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("fear_greed_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical Fear & Greed Index data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (daily for Fear & Greed)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized Fear & Greed events

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            # Calculate days to fetch
            days = (end - start).days + 1

            data = await self._client.get_index_data(limit=days)
            validate_fear_greed_data(data)
            events = parse_fear_greed_historical(data)

            logger.info(
                "fear_greed_historical_fetched",
                symbol=symbol,
                days=days,
                events_count=len(events),
            )

            return events

        except Exception as e:
            logger.error("fear_greed_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch historical Fear & Greed data: {e}") from e

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time Fear & Greed Index data.

        Note: Fear & Greed updates daily, so this polls at the configured interval.

        Args:
            symbols: List of symbols to subscribe to (ignored - crypto-wide metric)

        Yields:
            Standardized Fear & Greed events as they are updated

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info(
            "fear_greed_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                event = await self.get_current_index()
                if event:
                    yield event

            except Exception as e:
                logger.error("fear_greed_stream_error", error=str(e))

            # Wait for next poll
            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check Fear & Greed connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
        """
        return await self._client.health_check()

    async def get_current_index(self) -> StandardEvent:
        """Get current Fear & Greed Index value.

        Returns:
            StandardEvent containing current index data:
            - value: Index value (0-100)
            - classification: Sentiment label
            - sentiment: Normalized sentiment category
            - change: Change from previous day

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_index_data(limit=2)
            validate_fear_greed_data(data)
            event = parse_fear_greed_response(data)

            logger.info(
                "fear_greed_index_fetched",
                value=event.payload.get("value"),
                classification=event.payload.get("classification"),
            )

            return event

        except Exception as e:
            logger.error("fear_greed_index_error", error=str(e))
            raise RuntimeError(f"Failed to fetch Fear & Greed index: {e}") from e

    async def get_summary(self, days: int = 30) -> StandardEvent:
        """Get Fear & Greed Index summary with statistics.

        Args:
            days: Number of days for statistical analysis

        Returns:
            StandardEvent containing:
            - current: Current index value and classification
            - statistics: Average, min, max over period
            - distribution: Count per sentiment category
            - trend: Recent trend direction

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_index_data(limit=days)
            validate_fear_greed_data(data)
            event = parse_fear_greed_summary(data)

            logger.info(
                "fear_greed_summary_fetched",
                days=days,
                current_value=event.payload.get("current", {}).get("value"),
            )

            return event

        except Exception as e:
            logger.error("fear_greed_summary_error", error=str(e))
            raise RuntimeError(f"Failed to fetch Fear & Greed summary: {e}") from e

    async def get_historical(self, days: int = 30) -> list[dict[str, Any]]:
        """Get historical Fear & Greed Index data.

        Args:
            days: Number of days of history

        Returns:
            List of historical entries with:
            - timestamp: ISO timestamp
            - value: Index value
            - classification: Sentiment label

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_historical(days=days)
            return data

        except Exception as e:
            logger.error("fear_greed_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch historical data: {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
