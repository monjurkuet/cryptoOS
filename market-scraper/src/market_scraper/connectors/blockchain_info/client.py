# src/market_scraper/connectors/blockchain_info/client.py

"""HTTP client for Blockchain.info API interactions."""

import asyncio
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.blockchain_info.config import (
    BlockchainChartType,
    BlockchainInfoConfig,
)

logger = structlog.get_logger(__name__)


class BlockchainInfoClient:
    """HTTP client for fetching Blockchain.info data.

    This client handles all HTTP interactions with the Blockchain.info API,
    including connection management, request retries, and response handling.

    The Blockchain.info API provides Bitcoin network metrics including:
    - Hash rate and difficulty
    - Transaction counts
    - Unique addresses
    - Market price and market cap
    - Mempool statistics

    Attributes:
        config: Blockchain.info configuration
        _client: HTTP client (initialized on connect)
    """

    def __init__(self, config: BlockchainInfoConfig) -> None:
        """Initialize the Blockchain.info client.

        Args:
            config: Blockchain.info connector configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = asyncio.Lock()
        self._last_fetch_time: float = 0

    async def connect(self) -> None:
        """Establish HTTP connection pool.

        Creates and configures the HTTP session for API requests.

        Raises:
            ConnectionError: If connection pool initialization fails
        """
        if self._client is not None:
            return

        try:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MarketScraper/1.0",
                },
            )
            logger.info("blockchain_info_client_connected")
        except Exception as e:
            logger.error("blockchain_info_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize Blockchain.info client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool.

        Gracefully closes all connections and releases resources.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("blockchain_info_client_closed")

    async def get_chart_data(
        self,
        chart_type: BlockchainChartType,
        timespan: str | None = None,
    ) -> dict[str, Any]:
        """Fetch chart data from Blockchain.info.

        Args:
            chart_type: Type of chart to fetch (e.g., hash-rate, difficulty)
            timespan: Time span for data (e.g., '30days', '1year', 'all')

        Returns:
            Dictionary containing chart data with:
            - status: "ok" or error
            - name: Chart name
            - unit: Data unit
            - period: Data period
            - description: Chart description
            - values: List of {x: timestamp, y: value} points

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        if timespan is None:
            timespan = self.config.default_timespan

        url = f"{self.config.base_url}/{chart_type.value}"
        params = {
            "format": "json",
            "timespan": timespan,
        }
        if self.config.cors_enabled:
            params["cors"] = "true"

        async with self._rate_limiter:
            try:
                start_time = time.time()
                response = await self._client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                self._last_fetch_time = time.time()

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    "blockchain_info_chart_fetched",
                    chart=chart_type.value,
                    latency_ms=round(latency_ms, 2),
                    values_count=len(data.get("values", [])),
                )

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "blockchain_info_http_error",
                    chart=chart_type.value,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error(
                    "blockchain_info_request_error",
                    chart=chart_type.value,
                    error=str(e),
                )
                raise

    async def get_all_charts(
        self,
        timespan: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Fetch all enabled charts.

        Args:
            timespan: Time span for data

        Returns:
            Dictionary mapping chart type to chart data
        """
        results = {}
        for chart_type in self.config.enabled_charts:
            try:
                data = await self.get_chart_data(chart_type, timespan)
                results[chart_type.value] = data
            except Exception as e:
                logger.warning(
                    "blockchain_info_chart_failed",
                    chart=chart_type.value,
                    error=str(e),
                )
                results[chart_type.value] = {"error": str(e)}
        return results

    async def get_simple_query(self, query: str) -> str | int | float:
        """Fetch data from simple query API.

        Args:
            query: Query type (e.g., 'hashrate', 'getdifficulty', 'getblockcount')

        Returns:
            Raw response value (number or string)

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        url = f"{self.config.query_url}/{query}"

        async with self._rate_limiter:
            try:
                response = await self._client.get(url)
                response.raise_for_status()

                # Try to parse as number
                text = response.text.strip()
                try:
                    if "." in text:
                        return float(text)
                    return int(text)
                except ValueError:
                    return text

            except httpx.HTTPStatusError as e:
                logger.error(
                    "blockchain_info_query_error",
                    query=query,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise

    async def get_current_metrics(self) -> dict[str, Any]:
        """Get current network metrics from simple query API.

        Returns:
            Dictionary with current values for:
            - hash_rate: Current hash rate (GH/s)
            - difficulty: Current difficulty
            - block_count: Current block height
            - total_btc: Total BTC in circulation (satoshis)
            - price_24h: 24-hour average price (USD)
            - market_cap: Market capitalization (USD)
        """
        queries = {
            "hash_rate": "hashrate",
            "difficulty": "getdifficulty",
            "block_count": "getblockcount",
            "total_btc": "totalbc",
            "price_24h": "24hrprice",
            "market_cap": "marketcap",
            "tx_count_24h": "24hrtransactioncount",
        }

        results = {}
        for key, query in queries.items():
            try:
                results[key] = await self.get_simple_query(query)
            except Exception as e:
                logger.warning(
                    "blockchain_info_query_failed",
                    query=query,
                    error=str(e),
                )
                results[key] = None

        return results

    async def health_check(self) -> dict[str, Any]:
        """Check API health status.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time
            - message: Human-readable status
        """
        if self._client is None:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": "Client not connected",
            }

        try:
            start = time.time()
            await self.get_simple_query("getblockcount")
            latency = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": "API responding normally",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": str(e),
            }
