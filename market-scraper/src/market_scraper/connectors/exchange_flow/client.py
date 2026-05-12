# src/market_scraper/connectors/exchange_flow/client.py

"""HTTP client for fetching exchange flow data from Coin Metrics CSV.

Uses synchronous httpx.Client with asyncio.to_thread() to prevent
slow remote servers from blocking the event loop. CSV parsing is
also done in the thread.
"""

import asyncio
import csv
import io
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.exchange_flow.config import ExchangeFlowConfig

logger = structlog.get_logger(__name__)

# Hard timeout for CSV fetch + parse (seconds)
_EXCHANGE_FLOW_FETCH_TIMEOUT = 30.0


class ExchangeFlowClient:
    """HTTP client for fetching exchange flow data.

    Fetches Bitcoin exchange flow data from Coin Metrics Community CSV
    hosted on GitHub. No API key required. No rate limits.

    Uses sync httpx.Client + asyncio.to_thread() to avoid event loop blocking.

    Available metrics:
    - FlowInExNtv: Exchange inflow in BTC
    - FlowOutExNtv: Exchange outflow in BTC
    - SplyExNtv: Exchange supply in BTC
    """

    # Columns we care about
    EXCHANGE_FLOW_COLUMNS = [
        "time",
        "FlowInExNtv",
        "FlowOutExNtv",
        "SplyExNtv",
    ]

    def __init__(self, config: ExchangeFlowConfig) -> None:
        """Initialize the Exchange Flow client.

        Args:
            config: Exchange Flow connector configuration
        """
        self.config = config
        self._client: httpx.Client | None = None
        self._rate_limiter = asyncio.Lock()
        self._cache: dict[str, Any] | None = None
        self._cache_time: float = 0

    def connect(self) -> None:
        """Establish HTTP connection pool (sync)."""
        if self._client is not None:
            return

        try:
            self._client = httpx.Client(
                timeout=httpx.Timeout(20.0, connect=5.0, read=20.0, write=5.0),
                follow_redirects=True,
                headers={
                    "Accept": "text/csv",
                    "User-Agent": "MarketScraper/1.0",
                },
            )
            logger.info("exchange_flow_client_connected")
        except Exception as e:
            logger.error("exchange_flow_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize Exchange Flow client: {e}") from e

    def close(self) -> None:
        """Close HTTP connection pool (sync)."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("exchange_flow_client_closed")

    def _sync_fetch_and_parse(self, url: str, use_cache: bool = True) -> dict[str, Any]:
        """Synchronous fetch + parse — runs in thread pool.

        Args:
            url: CSV URL to fetch
            use_cache: Whether to return cached data if fresh

        Returns:
            Parsed data dict
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        response = self._client.get(url)
        response.raise_for_status()
        csv_content = response.text
        return self._parse_csv(csv_content)

    async def fetch_csv_data(self, use_cache: bool = True) -> dict[str, Any]:
        """Fetch and parse the Coin Metrics BTC CSV.

        Uses asyncio.to_thread() to prevent slow servers from blocking
        the event loop, with a hard wait_for timeout as safety net.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing:
            - dates: List of date strings
            - flow_in_btc: List of inflow values in BTC
            - flow_out_btc: List of outflow values in BTC
            - netflow_btc: List of netflow values (outflow - inflow)
            - supply_btc: List of exchange supply values

        Raises:
            asyncio.TimeoutError: If fetch exceeds timeout
            httpx.HTTPError: If the HTTP request fails
        """
        # Check cache
        if use_cache and self._cache is not None:
            cache_age = time.time() - self._cache_time
            if cache_age < self.config.cache_ttl_seconds:
                logger.debug("exchange_flow_cache_hit")
                return self._cache

        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        async with self._rate_limiter:
            try:
                start_time = time.time()

                # Run sync HTTP fetch + CSV parse in thread pool
                data = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._sync_fetch_and_parse,
                        str(self.config.csv_url),
                        use_cache,
                    ),
                    timeout=_EXCHANGE_FLOW_FETCH_TIMEOUT,
                )

                # Cache the result
                self._cache = data
                self._cache_time = time.time()

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    "exchange_flow_data_fetched",
                    latency_ms=round(latency_ms, 2),
                    data_points=len(data.get("dates", [])),
                )

                return data

            except TimeoutError:
                logger.error(
                    "exchange_flow_fetch_timeout",
                    timeout_s=_EXCHANGE_FLOW_FETCH_TIMEOUT,
                )
                raise
            except httpx.HTTPStatusError as e:
                logger.error(
                    "exchange_flow_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error("exchange_flow_request_error", error=str(e))
                raise

    def _parse_csv(self, csv_content: str) -> dict[str, Any]:
        """Parse CSV content into structured data.

        Args:
            csv_content: Raw CSV content

        Returns:
            Dictionary with parsed data
        """
        reader = csv.DictReader(io.StringIO(csv_content))

        dates = []
        flow_in_btc = []
        flow_out_btc = []
        supply_btc = []

        for row in reader:
            try:
                # Parse date
                date_str = row.get("time", "")
                if not date_str:
                    continue
                dates.append(date_str[:10])  # YYYY-MM-DD

                # Parse numeric values
                flow_in_btc.append(self._parse_float(row.get("FlowInExNtv")))
                flow_out_btc.append(self._parse_float(row.get("FlowOutExNtv")))
                supply_btc.append(self._parse_float(row.get("SplyExNtv")))

            except Exception as e:
                logger.warning("exchange_flow_row_parse_error", error=str(e))
                continue

        # Calculate netflow (outflow - inflow, positive = leaving exchanges = bullish)
        netflow_btc = []
        for i in range(len(flow_out_btc)):
            if flow_out_btc[i] is not None and flow_in_btc[i] is not None:
                netflow_btc.append(flow_out_btc[i] - flow_in_btc[i])
            else:
                netflow_btc.append(None)

        return {
            "dates": dates,
            "flow_in_btc": flow_in_btc,
            "flow_out_btc": flow_out_btc,
            "netflow_btc": netflow_btc,
            "supply_btc": supply_btc,
        }

    def _parse_float(self, value: str | None) -> float | None:
        """Parse a string to float.

        Args:
            value: String value to parse

        Returns:
            Float value or None
        """
        if value is None or value == "" or value == "null":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def get_latest_flows(self) -> dict[str, Any]:
        """Get the latest exchange flow values.

        Returns:
            Dictionary with latest values
        """
        data = await self.fetch_csv_data()

        # Find latest non-null values
        def get_latest(values: list) -> float | None:
            for i in range(len(values) - 1, -1, -1):
                if values[i] is not None:
                    return values[i]
            return None

        return {
            "date": data["dates"][-1] if data["dates"] else None,
            "flow_in_btc": get_latest(data["flow_in_btc"]),
            "flow_out_btc": get_latest(data["flow_out_btc"]),
            "netflow_btc": get_latest(data["netflow_btc"]),
            "supply_btc": get_latest(data["supply_btc"]),
        }

    async def get_flow_history(self, days: int = 30) -> dict[str, Any]:
        """Get historical exchange flow data.

        Args:
            days: Number of days of history

        Returns:
            Dictionary with historical data
        """
        data = await self.fetch_csv_data()

        # Get last N days
        return {
            "dates": data["dates"][-days:],
            "flow_in_btc": data["flow_in_btc"][-days:],
            "flow_out_btc": data["flow_out_btc"][-days:],
            "netflow_btc": data["netflow_btc"][-days:],
            "supply_btc": data["supply_btc"][-days:],
        }

    async def health_check(self) -> dict[str, Any]:
        """Check API health status.

        Returns:
            Health status dict
        """
        if self._client is None:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": "Client not connected",
            }

        try:
            start = time.time()
            await self.fetch_csv_data(use_cache=False)
            latency = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": "Exchange Flow API responding",
            }
        except TimeoutError:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": f"Fetch timed out after {_EXCHANGE_FLOW_FETCH_TIMEOUT}s",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": str(e),
            }
