# src/market_scraper/connectors/bitview/connector.py

"""Bitview (Bitcoin Research Kit) connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.bitview.client import BitviewClient
from market_scraper.connectors.bitview.config import BitviewConfig, BitviewMetric
from market_scraper.connectors.bitview.parsers import (
    parse_bitview_liveliness,
    parse_bitview_metric,
    parse_bitview_mvrv,
    parse_bitview_nupl,
    parse_bitview_puell,
    parse_bitview_realized_cap,
    parse_bitview_realized_price,
    parse_bitview_sopr,
    validate_bitview_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class BitviewConnector(DataConnector):
    """Connector for Bitview.space on-chain metrics (Bitcoin Research Kit).

    Bitview.space provides free Bitcoin on-chain metrics computed directly
    from a live Bitcoin node. No API key required.

    Available metrics:
    - SOPR: Spent Output Profit Ratio (with LTH/STH variants)
    - NUPL: Net Unrealized Profit/Loss (with LTH/STH variants)
    - MVRV: Market Value to Realized Value (with LTH/STH variants)
    - Realized Cap/Price: Aggregate cost basis
    - Liveliness: Network activity measure (alternative to dormancy)
    - Puell Multiple: Miner revenue indicator

    Attributes:
        config: Bitview-specific configuration
        client: HTTP client for API requests
    """

    # Metric-specific parsers
    METRIC_PARSERS = {
        "sopr": parse_bitview_sopr,
        "lth_sopr": parse_bitview_sopr,
        "sth_sopr": parse_bitview_sopr,
        "nupl": parse_bitview_nupl,
        "lth_nupl": parse_bitview_nupl,
        "sth_nupl": parse_bitview_nupl,
        "mvrv": parse_bitview_mvrv,
        "lth_mvrv": parse_bitview_mvrv,
        "sth_mvrv": parse_bitview_mvrv,
        "liveliness": parse_bitview_liveliness,
        "realized_cap": parse_bitview_realized_cap,
        "realized_price": parse_bitview_realized_price,
        "puell_multiple": parse_bitview_puell,
    }

    def __init__(self, config: BitviewConfig) -> None:
        """Initialize the Bitview connector.

        Args:
            config: Bitview connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = BitviewClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to Bitview."""
        try:
            await self._client.connect()
            self._connected = True
            logger.info("bitview_connector_connected")
        except Exception as e:
            logger.error("bitview_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Bitview: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to Bitview."""
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("bitview_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical Bitview data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (daily for Bitview)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized Bitview events

        Raises:
            RuntimeError: If fetch fails
        """
        events = []
        for metric in self.config.metrics:
            try:
                event = await self.get_metric(metric)
                events.append(event)
            except Exception as e:
                logger.warning(
                    "bitview_metric_fetch_failed",
                    metric=metric,
                    error=str(e),
                )

        logger.info("bitview_historical_fetched", events_count=len(events))
        return events

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time Bitview data.

        Note: Bitview data updates daily, so this polls at 24-hour intervals.

        Args:
            symbols: List of symbols to subscribe to (ignored - BTC only)

        Yields:
            Standardized Bitview events

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info(
            "bitview_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                for metric in self.config.metrics:
                    event = await self.get_metric(metric)
                    yield event
            except Exception as e:
                logger.error("bitview_stream_error", error=str(e))

            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check Bitview connector health.

        Returns:
            Health status dict
        """
        return await self._client.health_check()

    async def get_metric(self, metric: str | BitviewMetric) -> StandardEvent:
        """Get data for a specific metric.

        Args:
            metric: Metric name or enum

        Returns:
            StandardEvent containing metric data

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            metric_str = metric.value if isinstance(metric, BitviewMetric) else metric

            data = await self._client.get_metric_data(metric_str)
            validate_bitview_data(data)

            # Use metric-specific parser if available
            parser = self.METRIC_PARSERS.get(metric_str, parse_bitview_metric)
            event = parser(data)

            logger.info(
                "bitview_metric_fetched",
                metric=metric_str,
                value=event.payload.get("value"),
            )

            return event

        except Exception as e:
            logger.error("bitview_metric_error", metric=str(metric), error=str(e))
            raise RuntimeError(f"Failed to fetch Bitview metric '{metric}': {e}") from e

    async def get_sopr(self) -> StandardEvent:
        """Get SOPR (Spent Output Profit Ratio) data.

        SOPR measures whether coins are being sold at profit or loss.
        - SOPR > 1: Coins being sold at profit
        - SOPR < 1: Coins being sold at loss

        Returns:
            StandardEvent with SOPR data
        """
        return await self.get_metric(BitviewMetric.SOPR)

    async def get_sopr_lth(self) -> StandardEvent:
        """Get Long-term Holder SOPR.

        LTH SOPR tracks profit-taking behavior of long-term holders
        (coins held > 155 days).

        Returns:
            StandardEvent with LTH SOPR data
        """
        return await self.get_metric(BitviewMetric.SOPR_LTH)

    async def get_sopr_sth(self) -> StandardEvent:
        """Get Short-term Holder SOPR.

        STH SOPR tracks profit-taking behavior of short-term holders
        (coins held < 155 days).

        Returns:
            StandardEvent with STH SOPR data
        """
        return await self.get_metric(BitviewMetric.SOPR_STH)

    async def get_nupl(self) -> StandardEvent:
        """Get NUPL (Net Unrealized Profit/Loss) data.

        NUPL zones (normalized 0-1):
        - < 0: Capitulation
        - 0 - 0.25: Hope/Fear
        - 0.25 - 0.5: Optimism
        - 0.5 - 0.75: Belief
        - > 0.75: Euphoria

        Note: Bitview NUPL is scaled by 100 (e.g., 19.94 = 0.1994).

        Returns:
            StandardEvent with NUPL data
        """
        return await self.get_metric(BitviewMetric.NUPL)

    async def get_mvrv(self) -> StandardEvent:
        """Get MVRV (Market Value to Realized Value) data.

        MVRV signals:
        - < 1.0: Undervalued
        - > 3.5: Overvalued

        Returns:
            StandardEvent with MVRV data
        """
        return await self.get_metric(BitviewMetric.MVRV)

    async def get_liveliness(self) -> StandardEvent:
        """Get Liveliness data.

        Liveliness = 1 - (cumulative CDD / cumulative coin days)
        Alternative to dormancy - measures network activity.

        Returns:
            StandardEvent with Liveliness data
        """
        return await self.get_metric(BitviewMetric.LIVELINESS)

    async def get_realized_cap(self) -> StandardEvent:
        """Get Realized Cap data.

        Returns:
            StandardEvent with Realized Cap data (in USD)
        """
        return await self.get_metric(BitviewMetric.REALIZED_CAP)

    async def get_realized_price(self) -> StandardEvent:
        """Get Realized Price data.

        Returns:
            StandardEvent with Realized Price data (in USD)
        """
        return await self.get_metric(BitviewMetric.REALIZED_PRICE)

    async def get_puell_multiple(self) -> StandardEvent:
        """Get Puell Multiple data.

        Returns:
            StandardEvent with Puell Multiple data
        """
        return await self.get_metric(BitviewMetric.PUELL_MULTIPLE)

    async def get_all_sopr_metrics(self) -> dict[str, StandardEvent]:
        """Get all SOPR variants at once.

        Returns:
            Dict with 'sopr', 'lth', 'sth' keys
        """
        sopr, lth, sth = await asyncio.gather(
            self.get_sopr(),
            self.get_sopr_lth(),
            self.get_sopr_sth(),
        )

        return {
            "sopr": sopr,
            "lth": lth,
            "sth": sth,
        }

    async def get_summary(self) -> dict[str, Any]:
        """Get a summary of key Bitview metrics.

        Returns:
            Dictionary with latest values for key metrics
        """
        try:
            # Fetch key metrics in parallel
            tasks = [
                self.get_sopr(),
                self.get_sopr_lth(),
                self.get_sopr_sth(),
                self.get_nupl(),
                self.get_mvrv(),
                self.get_liveliness(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            summary = {
                "timestamp": datetime.now(UTC).isoformat(),
                "sopr": None,
                "sopr_lth": None,
                "sopr_sth": None,
                "nupl": None,
                "mvrv": None,
                "liveliness": None,
            }

            metric_names = ["sopr", "sopr_lth", "sopr_sth", "nupl", "mvrv", "liveliness"]

            for name, result in zip(metric_names, results, strict=False):
                if not isinstance(result, Exception):
                    summary[name] = {
                        "value": result.payload.get("value"),
                        "date": result.payload.get("date"),
                        "interpretation": result.payload.get("interpretation"),
                        "signal": result.payload.get("signal"),
                        "zone": result.payload.get("zone"),
                    }

            return summary

        except Exception as e:
            logger.error("bitview_summary_error", error=str(e))
            raise RuntimeError(f"Failed to get Bitview summary: {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
