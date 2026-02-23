# src/market_scraper/connectors/chainexposed/connector.py

"""ChainExposed connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.chainexposed.client import ChainExposedClient
from market_scraper.connectors.chainexposed.config import ChainExposedConfig, ChainExposedMetric
from market_scraper.connectors.chainexposed.parsers import (
    parse_chainexposed_dormancy,
    parse_chainexposed_hodl_waves,
    parse_chainexposed_metric,
    parse_chainexposed_mvrv,
    parse_chainexposed_nupl,
    parse_chainexposed_sopr,
    validate_chainexposed_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class ChainExposedConnector(DataConnector):
    """Connector for ChainExposed.com on-chain metrics.

    ChainExposed.com provides free Bitcoin on-chain metrics by embedding
    data as JavaScript arrays in HTML pages. No API key required, no rate limits.

    Available metrics:
    - SOPR: Spent Output Profit Ratio
    - SOPR_LTH: Long-term holder SOPR
    - SOPR_STH: Short-term holder SOPR
    - MVRV: Market Value to Realized Value
    - NUPL: Net Unrealized Profit/Loss
    - DORMANCY: Average dormancy
    - HODL_WAVES: Coin age distribution

    Attributes:
        config: ChainExposed-specific configuration
        client: HTTP client for web scraping
    """

    # Metric-specific parsers
    METRIC_PARSERS = {
        "SOPR": parse_chainexposed_sopr,
        "XthSOPRLongTermHolderCoin": parse_chainexposed_sopr,
        "XthSOPRShortTermHolderCoin": parse_chainexposed_sopr,
        "NUPL": parse_chainexposed_nupl,
        "MVRV": parse_chainexposed_mvrv,
        "XthMVRVLongTermHolderAddress": parse_chainexposed_mvrv,
        "XthMVRVShortTermHolderAddress": parse_chainexposed_mvrv,
        "Dormancy": parse_chainexposed_dormancy,
        "DormancyFlow": parse_chainexposed_dormancy,
        "HodlWavesAbsolute": parse_chainexposed_hodl_waves,
        "HodlWavesRelative": parse_chainexposed_hodl_waves,
    }

    def __init__(self, config: ChainExposedConfig) -> None:
        """Initialize the ChainExposed connector.

        Args:
            config: ChainExposed connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = ChainExposedClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection to ChainExposed."""
        try:
            await self._client.connect()
            self._connected = True
            logger.info("chainexposed_connector_connected")
        except Exception as e:
            logger.error("chainexposed_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to ChainExposed: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection to ChainExposed."""
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("chainexposed_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical ChainExposed data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (daily for ChainExposed)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized ChainExposed events

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
                    "chainexposed_metric_fetch_failed",
                    metric=metric,
                    error=str(e),
                )

        logger.info("chainexposed_historical_fetched", events_count=len(events))
        return events

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time ChainExposed data.

        Note: ChainExposed data updates daily, so this polls at 24-hour intervals.

        Args:
            symbols: List of symbols to subscribe to (ignored - BTC only)

        Yields:
            Standardized ChainExposed events

        Raises:
            RuntimeError: If streaming encounters an unrecoverable error
        """
        self._running = True
        logger.info(
            "chainexposed_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                for metric in self.config.metrics:
                    event = await self.get_metric(metric)
                    yield event
            except Exception as e:
                logger.error("chainexposed_stream_error", error=str(e))

            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check ChainExposed connector health.

        Returns:
            Health status dict
        """
        return await self._client.health_check()

    async def get_metric(self, metric: str | ChainExposedMetric) -> StandardEvent:
        """Get data for a specific metric.

        Args:
            metric: Metric name or enum

        Returns:
            StandardEvent containing metric data

        Raises:
            RuntimeError: If fetch fails
        """
        try:
            metric_str = metric.value if isinstance(metric, ChainExposedMetric) else metric

            data = await self._client.get_metric_data(metric_str)
            validate_chainexposed_data(data)

            # Use metric-specific parser if available
            parser = self.METRIC_PARSERS.get(metric_str, parse_chainexposed_metric)
            event = parser(data)

            logger.info(
                "chainexposed_metric_fetched",
                metric=metric_str,
                value=event.payload.get("value"),
            )

            return event

        except Exception as e:
            logger.error("chainexposed_metric_error", metric=str(metric), error=str(e))
            raise RuntimeError(f"Failed to fetch ChainExposed metric '{metric}': {e}") from e

    async def get_sopr(self) -> StandardEvent:
        """Get SOPR (Spent Output Profit Ratio) data.

        SOPR measures whether coins are being sold at profit or loss.
        - SOPR > 1: Coins being sold at profit
        - SOPR < 1: Coins being sold at loss

        Returns:
            StandardEvent with SOPR data
        """
        return await self.get_metric(ChainExposedMetric.SOPR)

    async def get_sopr_lth(self) -> StandardEvent:
        """Get Long-term Holder SOPR.

        LTH SOPR tracks profit-taking behavior of long-term holders
        (coins held > 155 days).

        Returns:
            StandardEvent with LTH SOPR data
        """
        return await self.get_metric(ChainExposedMetric.SOPR_LTH)

    async def get_sopr_sth(self) -> StandardEvent:
        """Get Short-term Holder SOPR.

        STH SOPR tracks profit-taking behavior of short-term holders
        (coins held < 155 days).

        Returns:
            StandardEvent with STH SOPR data
        """
        return await self.get_metric(ChainExposedMetric.SOPR_STH)

    async def get_nupl(self) -> StandardEvent:
        """Get NUPL (Net Unrealized Profit/Loss) data.

        NUPL zones:
        - < 0: Capitulation
        - 0 - 0.25: Hope/Fear
        - 0.25 - 0.5: Optimism
        - 0.5 - 0.75: Belief
        - > 0.75: Euphoria

        Returns:
            StandardEvent with NUPL data
        """
        return await self.get_metric(ChainExposedMetric.NUPL)

    async def get_mvrv(self) -> StandardEvent:
        """Get MVRV (Market Value to Realized Value) data.

        MVRV signals:
        - < 1.0: Undervalued
        - > 3.5: Overvalued

        Returns:
            StandardEvent with MVRV data
        """
        return await self.get_metric(ChainExposedMetric.MVRV)

    async def get_dormancy(self) -> StandardEvent:
        """Get Dormancy data.

        Dormancy measures the average number of days destroyed per coin transacted.
        Higher values indicate older coins moving (potential distribution).

        Returns:
            StandardEvent with Dormancy data
        """
        return await self.get_metric(ChainExposedMetric.DORMANCY)

    async def get_hodl_waves(self) -> StandardEvent:
        """Get HODL Waves data.

        HODL Waves shows the distribution of Bitcoin supply by age bands.

        Returns:
            StandardEvent with HODL Waves band distribution
        """
        return await self.get_metric(ChainExposedMetric.HODL_WAVES_ABSOLUTE)

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
        """Get a summary of key ChainExposed metrics.

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
                self.get_dormancy(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            summary = {
                "timestamp": datetime.now(UTC).isoformat(),
                "sopr": None,
                "sopr_lth": None,
                "sopr_sth": None,
                "nupl": None,
                "mvrv": None,
                "dormancy": None,
            }

            metric_names = ["sopr", "sopr_lth", "sopr_sth", "nupl", "mvrv", "dormancy"]

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
            logger.error("chainexposed_summary_error", error=str(e))
            raise RuntimeError(f"Failed to get ChainExposed summary: {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
