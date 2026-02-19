# src/market_scraper/connectors/blockchain_info/connector.py

"""Blockchain.info connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.blockchain_info.client import BlockchainInfoClient
from market_scraper.connectors.blockchain_info.config import (
    BlockchainChartType,
    BlockchainInfoConfig,
)
from market_scraper.connectors.blockchain_info.parsers import (
    parse_all_charts_response,
    parse_chart_historical,
    parse_chart_response,
    parse_current_metrics,
    validate_chart_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class BlockchainInfoConnector(DataConnector):
    """Connector for Blockchain.info Bitcoin network data.

    Provides access to Bitcoin network metrics including:
    - Hash rate and difficulty
    - Transaction counts and unique addresses
    - Market price and market cap
    - Mempool statistics

    The Blockchain.info API is free and provides reliable historical
    data for Bitcoin network metrics.

    Attributes:
        config: Blockchain.info-specific configuration
        client: HTTP client for API interactions
    """

    def __init__(self, config: BlockchainInfoConfig) -> None:
        """Initialize the Blockchain.info connector.

        Args:
            config: Blockchain.info connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = BlockchainInfoClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Blockchain.info API.

        Initializes the HTTP client and verifies connectivity.

        Raises:
            ConnectionError: If connection fails after retries
        """
        try:
            await self._client.connect()
            self._connected = True
            logger.info("blockchain_info_connector_connected")
        except Exception as e:
            logger.error("blockchain_info_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Blockchain.info: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to Blockchain.info.

        Closes HTTP sessions and releases resources.
        """
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("blockchain_info_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical Blockchain.info chart data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (e.g., "1d")
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized chart events

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            # Calculate timespan from date range
            days = (end - start).days
            timespan = f"{days}days" if days > 0 else "30days"

            events = []
            for chart_type in self.config.enabled_charts:
                try:
                    data = await self._client.get_chart_data(chart_type, timespan)
                    validate_chart_data(data)
                    chart_events = parse_chart_historical(data, chart_type)
                    events.extend(chart_events)
                except Exception as e:
                    logger.warning(
                        "blockchain_info_chart_fetch_failed",
                        chart=chart_type.value,
                        error=str(e),
                    )

            logger.info(
                "blockchain_info_historical_fetched",
                symbol=symbol,
                events_count=len(events),
            )

            return events

        except Exception as e:
            logger.error("blockchain_info_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch historical Blockchain.info data: {e}") from e

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time Blockchain.info data.

        Note: Blockchain.info API is polled at configured intervals.

        Args:
            symbols: List of symbols to subscribe to (ignored - BTC only)

        Yields:
            Standardized Blockchain.info events as they are updated

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info(
            "blockchain_info_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                # Fetch current metrics
                metrics = await self._client.get_current_metrics()
                event = parse_current_metrics(metrics)
                yield event

            except Exception as e:
                logger.error("blockchain_info_stream_error", error=str(e))

            # Wait for next poll
            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check Blockchain.info connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
        """
        return await self._client.health_check()

    async def get_chart(
        self,
        chart_type: BlockchainChartType,
        timespan: str | None = None,
    ) -> StandardEvent:
        """Get data for a specific chart.

        Args:
            chart_type: Type of chart to fetch
            timespan: Time span for data (e.g., '30days', '1year')

        Returns:
            StandardEvent containing chart data

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_chart_data(chart_type, timespan)
            validate_chart_data(data)
            event = parse_chart_response(data, chart_type)

            logger.info(
                "blockchain_info_chart_fetched",
                chart=chart_type.value,
                values_count=event.payload.get("values_count"),
            )

            return event

        except Exception as e:
            logger.error(
                "blockchain_info_chart_error",
                chart=chart_type.value,
                error=str(e),
            )
            raise RuntimeError(f"Failed to fetch chart '{chart_type.value}': {e}") from e

    async def get_all_charts(
        self,
        timespan: str | None = None,
    ) -> StandardEvent:
        """Get data for all enabled charts.

        Args:
            timespan: Time span for data

        Returns:
            StandardEvent containing all chart data

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            charts_data = await self._client.get_all_charts(timespan)
            event = parse_all_charts_response(charts_data)

            logger.info(
                "blockchain_info_all_charts_fetched",
                charts_count=event.payload.get("charts_fetched"),
            )

            return event

        except Exception as e:
            logger.error("blockchain_info_all_charts_error", error=str(e))
            raise RuntimeError(f"Failed to fetch all charts: {e}") from e

    async def get_current_metrics(self) -> StandardEvent:
        """Get current Bitcoin network metrics.

        Returns:
            StandardEvent containing current metrics:
            - hash_rate_ghs: Network hash rate in GH/s
            - difficulty: Mining difficulty
            - block_height: Current block height
            - total_btc: Total BTC in circulation
            - price_usd: 24-hour average price
            - market_cap_usd: Market capitalization

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            metrics = await self._client.get_current_metrics()
            event = parse_current_metrics(metrics)

            logger.info(
                "blockchain_info_metrics_fetched",
                block_height=event.payload.get("block_height"),
            )

            return event

        except Exception as e:
            logger.error("blockchain_info_metrics_error", error=str(e))
            raise RuntimeError(f"Failed to fetch current metrics: {e}") from e

    async def get_network_summary(self) -> dict[str, Any]:
        """Get comprehensive network summary combining all data sources.

        Returns:
            Dictionary with:
            - current_metrics: Real-time values from simple query API
            - charts: Historical data from charts API
            - timestamp: When data was fetched
        """
        try:
            # Fetch from both APIs in parallel
            import asyncio

            current_task = self._client.get_current_metrics()
            charts_task = self._client.get_all_charts()

            current_metrics, charts_data = await asyncio.gather(
                current_task, charts_task, return_exceptions=True
            )

            summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "current_metrics": current_metrics if not isinstance(current_metrics, Exception) else None,
                "charts": {},
            }

            # Process charts data
            if not isinstance(charts_data, Exception):
                for chart_name, data in charts_data.items():
                    if data.get("status") == "ok" and data.get("values"):
                        latest = data["values"][-1]
                        summary["charts"][chart_name] = {
                            "value": latest["y"],
                            "unit": data.get("unit"),
                            "timestamp": datetime.fromtimestamp(
                                latest["x"]
                            ).isoformat(),
                        }

            return summary

        except Exception as e:
            logger.error("blockchain_info_summary_error", error=str(e))
            raise RuntimeError(f"Failed to fetch network summary: {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
