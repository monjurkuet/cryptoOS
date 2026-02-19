# src/market_scraper/connectors/cbbi/connector.py

"""CBBI connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.cbbi.client import CBBIClient
from market_scraper.connectors.cbbi.config import CBBIConfig
from market_scraper.connectors.cbbi.parsers import (
    parse_cbbi_index_response,
    parse_cbbi_historical_response,
    parse_cbbi_component_response,
    validate_cbbi_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class CBBIConnector(DataConnector):
    """Connector for CBBI (Colin Talks Crypto Bitcoin Index) data.

    CBBI provides a comprehensive sentiment index for Bitcoin by aggregating
    various on-chain and market metrics. This connector fetches both current
    and historical CBBI data.

    CBBI data updates approximately once per day, so the connector polls
    at 24-hour intervals by default.

    Attributes:
        config: CBBI-specific configuration
        client: HTTP client for API interactions
    """

    def __init__(self, config: CBBIConfig) -> None:
        """Initialize the CBBI connector.

        Args:
            config: CBBI connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = CBBIClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to CBBI data source.

        Initializes the HTTP client and verifies connectivity.

        Raises:
            ConnectionError: If connection fails after retries
        """
        try:
            await self._client.connect()
            logger.info("cbbi_connector_connected")
        except Exception as e:
            logger.error("cbbi_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to CBBI: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to CBBI.

        Closes HTTP sessions and releases resources.
        """
        self._running = False
        await self._client.close()
        logger.info("cbbi_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical CBBI index data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD" for CBBI)
            timeframe: Data granularity (CBBI provides daily data)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized CBBI index events

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            # Calculate days range
            days = (end - start).days + 1
            if days <= 0:
                days = self.config.historical_days

            # Fetch raw data
            data = await self._client.get_index_data()

            # Validate and parse
            validate_cbbi_data(data)
            events = parse_cbbi_historical_response(data, days=days)

            logger.info(
                "cbbi_historical_fetched",
                symbol=symbol,
                days=days,
                events_count=len(events),
            )

            return events

        except Exception as e:
            logger.error("cbbi_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch historical CBBI data: {e}") from e

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time CBBI data.

        Note: CBBI updates approximately once per day, so this stream
        polls the API at 24-hour intervals.

        Args:
            symbols: List of symbols to subscribe to (ignored for CBBI
                    as it only tracks Bitcoin)

        Yields:
            Standardized CBBI index events as they are updated

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info("cbbi_stream_started", interval_seconds=self.config.update_interval_seconds)

        while self._running:
            try:
                event = await self.get_current_index()
                if event:
                    yield event

            except Exception as e:
                logger.error("cbbi_stream_error", error=str(e))

            # Wait for next poll (default: 24 hours since CBBI updates daily)
            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check CBBI connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
            - last_update: Timestamp of last successful data fetch
        """
        return await self._client.health_check()

    async def get_current_index(self) -> StandardEvent:
        """Get current CBBI index value.

        Convenience method to fetch the current index without
        specifying date range.

        Returns:
            StandardEvent containing current CBBI data

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_index_data()
            validate_cbbi_data(data)
            event = parse_cbbi_index_response(data)

            logger.info(
                "cbbi_index_fetched",
                confidence=event.payload.get("confidence"),
            )

            return event

        except Exception as e:
            logger.error("cbbi_index_error", error=str(e))
            raise RuntimeError(f"Failed to fetch CBBI index: {e}") from e

    async def get_component_breakdown(self) -> list[StandardEvent]:
        """Get breakdown of all CBBI components.

        Returns:
            List of StandardEvents, one per component metric

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_index_data()
            events = []

            # Component names from CBBI API (actual field names)
            component_names = [
                "PiCycle",
                "RUPL",
                "RHODL",
                "Puell",
                "2YMA",
                "MVRV",
                "ReserveRisk",
                "Woobull",
                "Trolololo",
            ]

            for name in component_names:
                try:
                    event = parse_cbbi_component_response(data, name)
                    events.append(event)
                except ValueError:
                    # Component not in data, skip
                    continue

            logger.info("cbbi_components_fetched", count=len(events))
            return events

        except Exception as e:
            logger.error("cbbi_components_error", error=str(e))
            raise RuntimeError(f"Failed to fetch CBBI components: {e}") from e

    async def get_specific_component(self, component: str) -> StandardEvent:
        """Get data for a specific CBBI component.

        Args:
            component: Component name (e.g., "MVRV", "Puell", "PiCycleTop")

        Returns:
            StandardEvent containing component data

        Raises:
            ValueError: If component name is invalid
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_index_data()
            event = parse_cbbi_component_response(data, component)

            logger.info("cbbi_component_fetched", component=component)
            return event

        except ValueError:
            raise
        except Exception as e:
            logger.error("cbbi_component_error", component=component, error=str(e))
            raise RuntimeError(f"Failed to fetch CBBI component '{component}': {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
