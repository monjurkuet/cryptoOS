# src/market_scraper/connectors/exchange_flow/connector.py

"""Exchange Flow connector implementation."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import structlog

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.exchange_flow.client import ExchangeFlowClient
from market_scraper.connectors.exchange_flow.config import ExchangeFlowConfig
from market_scraper.connectors.exchange_flow.parsers import (
    parse_exchange_flow_data,
    parse_exchange_flow_summary,
    validate_exchange_flow_data,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe

logger = structlog.get_logger(__name__)


class ExchangeFlowConnector(DataConnector):
    """Connector for Bitcoin exchange flow data.

    Fetches exchange flow data from Coin Metrics Community CSV hosted on GitHub.
    No API key required. No rate limits.

    Available metrics:
    - Flow In: BTC flowing into exchanges
    - Flow Out: BTC flowing out of exchanges
    - Netflow: Outflow - Inflow (positive = leaving exchanges = bullish)
    - Exchange Supply: Total BTC on exchanges

    Interpretation:
    - Positive netflow: BTC leaving exchanges (potential buying pressure)
    - Negative netflow: BTC entering exchanges (potential selling pressure)
    - Decreasing exchange supply: Long-term holders accumulating

    Attributes:
        config: Exchange Flow-specific configuration
        client: HTTP client for fetching CSV
    """

    def __init__(self, config: ExchangeFlowConfig) -> None:
        """Initialize the Exchange Flow connector.

        Args:
            config: Exchange Flow connector configuration
        """
        super().__init__(config)
        self.config = config
        self._client = ExchangeFlowClient(config)
        self._running = False

    async def connect(self) -> None:
        """Establish connection and fetch initial data."""
        try:
            await self._client.connect()
            self._connected = True
            logger.info("exchange_flow_connector_connected")
        except Exception as e:
            logger.error("exchange_flow_connector_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to connect to Exchange Flow: {e}") from e

    async def disconnect(self) -> None:
        """Gracefully close connection."""
        self._running = False
        self._connected = False
        await self._client.close()
        logger.info("exchange_flow_connector_disconnected")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical exchange flow data.

        Args:
            symbol: Trading pair/symbol (typically "BTC-USD")
            timeframe: Data granularity (daily for exchange flow)
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized exchange flow events
        """
        try:
            data = await self._client.fetch_csv_data()
            validate_exchange_flow_data(data)
            event = parse_exchange_flow_data(data)
            return [event]
        except Exception as e:
            logger.error("exchange_flow_historical_error", error=str(e))
            raise RuntimeError(f"Failed to fetch exchange flow data: {e}") from e

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream exchange flow data (polls daily).

        Args:
            symbols: List of symbols to subscribe to (ignored - BTC only)

        Yields:
            Standardized exchange flow events
        """
        self._running = True
        logger.info(
            "exchange_flow_stream_started",
            interval_seconds=self.config.update_interval_seconds,
        )

        while self._running:
            try:
                event = await self.get_current_flows()
                yield event
            except Exception as e:
                logger.error("exchange_flow_stream_error", error=str(e))

            await asyncio.sleep(self.config.update_interval_seconds)

    async def health_check(self) -> dict[str, Any]:
        """Check connector health.

        Returns:
            Health status dict
        """
        return await self._client.health_check()

    async def get_current_flows(self) -> StandardEvent:
        """Get current exchange flow data.

        Returns:
            StandardEvent with current flow data
        """
        try:
            data = await self._client.fetch_csv_data()
            validate_exchange_flow_data(data)
            event = parse_exchange_flow_summary(data)

            logger.info(
                "exchange_flow_fetched",
                netflow=event.payload.get("netflow_btc"),
                supply=event.payload.get("supply_btc"),
            )

            return event

        except Exception as e:
            logger.error("exchange_flow_fetch_error", error=str(e))
            raise RuntimeError(f"Failed to fetch exchange flow data: {e}") from e

    async def get_flow_history(self, days: int = 30) -> StandardEvent:
        """Get historical exchange flow data.

        Args:
            days: Number of days of history

        Returns:
            StandardEvent with historical data
        """
        try:
            data = await self._client.get_flow_history(days=days)
            event = parse_exchange_flow_data(data)

            logger.info("exchange_flow_history_fetched", days=days)

            return event

        except Exception as e:
            logger.error("exchange_flow_history_error", error=str(e))
            raise RuntimeError(f"Failed to fetch exchange flow history: {e}") from e

    async def get_netflow_summary(self) -> dict[str, Any]:
        """Get a summary of netflow metrics.

        Returns:
            Dictionary with netflow analysis
        """
        try:
            data = await self._client.fetch_csv_data()

            # Calculate various metrics
            netflow = data.get("netflow_btc", [])
            supply = data.get("supply_btc", [])
            dates = data.get("dates", [])

            # Find latest values
            def get_latest(values: list) -> float | None:
                for i in range(len(values) - 1, -1, -1):
                    if values[i] is not None:
                        return values[i]
                return None

            latest_netflow = get_latest(netflow)
            latest_supply = get_latest(supply)
            latest_date = dates[-1] if dates else None

            # Calculate averages
            valid_netflow = [v for v in netflow if v is not None]
            avg_7d = sum(valid_netflow[-7:]) / 7 if len(valid_netflow) >= 7 else None
            avg_30d = sum(valid_netflow[-30:]) / 30 if len(valid_netflow) >= 30 else None

            # Calculate cumulative netflow (last 7 days)
            cum_7d = sum([v for v in netflow[-7:] if v is not None]) if len(netflow) >= 7 else None

            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "date": latest_date,
                "netflow_btc": latest_netflow,
                "netflow_interpretation": "bullish"
                if latest_netflow and latest_netflow > 0
                else "bearish",
                "exchange_supply_btc": latest_supply,
                "netflow_7d_avg": avg_7d,
                "netflow_30d_avg": avg_30d,
                "cumulative_netflow_7d": cum_7d,
            }

        except Exception as e:
            logger.error("exchange_flow_summary_error", error=str(e))
            raise RuntimeError(f"Failed to get netflow summary: {e}") from e

    def stop(self) -> None:
        """Stop the streaming loop."""
        self._running = False
