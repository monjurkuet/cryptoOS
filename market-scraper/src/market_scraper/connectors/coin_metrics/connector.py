# src/market_scraper/connectors/coin_metrics/connector.py

"""Coin Metrics connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.coin_metrics.client import CoinMetricsClient
from market_scraper.connectors.coin_metrics.config import (
    CoinMetricsConfig,
    CoinMetricsMetric,
)
from market_scraper.connectors.coin_metrics.parsers import (
    parse_metrics_historical,
    parse_metrics_response,
    parse_single_metric,
    validate_metrics_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class CoinMetricsConnector(DataConnector):
    """Connector for Coin Metrics Community API data.

    Provides access to Bitcoin metrics from Coin Metrics Community API,
    which offers free access to basic cryptocurrency metrics without
    requiring an API key.

    Available metrics (free tier):
    - AdrActCnt: Active addresses count
    - TxCnt: Transaction count
    - BlkCnt: Block count
    - SplyCur: Current circulating supply

    Note: Price data is available from Hyperliquid candles. Advanced metrics
    like MVRV, Realized Cap require paid subscription.

    Attributes:
        config: Coin Metrics-specific configuration
        client: HTTP client for API interactions
    """

    def __init__(self, config: CoinMetricsConfig) -> None:
        """Initialize the Coin Metrics connector.

        Args:
            config: Coin Metrics connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = CoinMetricsClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Coin Metrics API.

        Initializes the HTTP client and verifies connectivity.

        Raises:
            ConnectionError: If connection fails after retries
        """
        try:
            await self._client.connect()
            self._connected = True
            logger.info("coin_metrics_connector_connected")
        except Exception as e:
            logger.error("coin_metrics_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Coin Metrics: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to Coin Metrics.

        Closes HTTP sessions and releases resources.
        """
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("coin_metrics_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical Coin Metrics data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (daily for Coin Metrics)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized Coin Metrics events

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_asset_metrics(
                asset=self.config.asset,
                metrics=self.config.metrics,
                start_time=start.strftime("%Y-%m-%d"),
                end_time=end.strftime("%Y-%m-%d"),
            )
            validate_metrics_data(data)
            events = parse_metrics_historical(data)

            logger.info(
                "coin_metrics_historical_fetched",
                symbol=symbol,
                events_count=len(events),
            )

            return events

        except Exception as e:
            logger.error("coin_metrics_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch historical Coin Metrics data: {e}") from e

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time Coin Metrics data.

        Note: Coin Metrics data is typically daily, so this polls at
        the configured interval.

        Args:
            symbols: List of symbols to subscribe to (ignored - uses config.asset)

        Yields:
            Standardized Coin Metrics events as they are updated

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info(
            "coin_metrics_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                event = await self.get_latest_metrics()
                if event:
                    yield event

            except Exception as e:
                logger.error("coin_metrics_stream_error", error=str(e))

            # Wait for next poll
            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check Coin Metrics connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
        """
        return await self._client.health_check()

    async def get_latest_metrics(
        self,
        asset: str | None = None,
        metrics: list[str] | None = None,
    ) -> StandardEvent:
        """Get latest metrics for an asset.

        Args:
            asset: Asset symbol (default: config.asset)
            metrics: List of metrics to fetch (default: config.metrics)

        Returns:
            StandardEvent containing latest metric values

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            data = await self._client.get_asset_metrics(
                asset=asset or self.config.asset,
                metrics=metrics or self.config.metrics,
                start_time=(datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%d"),
                end_time=datetime.now(UTC).strftime("%Y-%m-%d"),
            )
            validate_metrics_data(data)
            event = parse_metrics_response(data)

            logger.info(
                "coin_metrics_latest_fetched",
                asset=asset or self.config.asset,
                metrics_count=event.payload.get("metrics_count"),
            )

            return event

        except Exception as e:
            logger.error("coin_metrics_latest_error", error=str(e))
            raise RuntimeError(f"Failed to fetch latest metrics: {e}") from e

    async def get_metric_history(
        self,
        metric: str | CoinMetricsMetric,
        days: int = 30,
        asset: str | None = None,
    ) -> StandardEvent:
        """Get historical data for a specific metric.

        Args:
            metric: Metric ID or enum
            days: Number of days of history
            asset: Asset symbol

        Returns:
            StandardEvent containing:
            - metric_name: Metric identifier
            - current_value: Latest value
            - historical: List of historical values
            - statistics: Mean, min, max

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            metric_str = metric.value if isinstance(metric, CoinMetricsMetric) else metric

            data = await self._client.get_metric_history(
                metric=metric_str,
                asset=asset,
                days=days,
            )

            event = parse_single_metric({"data": data}, metric_str)

            logger.info(
                "coin_metrics_metric_history_fetched",
                metric=metric_str,
                days=days,
                current_value=event.payload.get("current_value"),
            )

            return event

        except Exception as e:
            logger.error(
                "coin_metrics_metric_history_error",
                metric=str(metric),
                error=str(e),
            )
            raise RuntimeError(f"Failed to fetch metric history: {e}") from e

    async def get_network_stats(self, asset: str | None = None) -> dict[str, Any]:
        """Get network statistics.

        Convenience method for fetching network activity metrics.

        Args:
            asset: Asset symbol

        Returns:
            Dictionary with network statistics
        """
        metrics = [
            CoinMetricsMetric.ACTIVE_ADDRESSES.value,
            CoinMetricsMetric.TRANSACTION_COUNT.value,
            CoinMetricsMetric.BLOCK_COUNT.value,
        ]

        event = await self.get_latest_metrics(asset=asset, metrics=metrics)
        metrics_data = event.payload.get("metrics", {})

        return {
            "active_addresses": metrics_data.get("AdrActCnt"),
            "transaction_count": metrics_data.get("TxCnt"),
            "block_count": metrics_data.get("BlkCnt"),
            "timestamp": event.payload.get("timestamp"),
        }

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
