# src/market_scraper/connectors/fear_greed/client.py

"""HTTP client for Fear & Greed Index API interactions."""

import asyncio
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.fear_greed.config import FearGreedConfig

logger = structlog.get_logger(__name__)


class FearGreedClient:
    """HTTP client for fetching Fear & Greed Index data.

    This client handles all HTTP interactions with the Alternative.me
    Fear & Greed API, including connection management and response handling.

    The Fear & Greed Index ranges from 0 (Extreme Fear) to 100 (Extreme Greed)
    and is updated daily.

    Attributes:
        config: Fear & Greed configuration
        _client: HTTP client (initialized on connect)
    """

    def __init__(self, config: FearGreedConfig) -> None:
        """Initialize the Fear & Greed client.

        Args:
            config: Fear & Greed connector configuration
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
            logger.info("fear_greed_client_connected")
        except Exception as e:
            logger.error("fear_greed_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize Fear & Greed client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool.

        Gracefully closes all connections and releases resources.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("fear_greed_client_closed")

    async def get_index_data(
        self,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Fetch Fear & Greed Index data.

        Args:
            limit: Number of results to return (0 = all available)

        Returns:
            Dictionary containing:
            - name: "Fear and Greed Index"
            - data: List of {value, value_classification, timestamp}
            - metadata: {error: null}

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        if limit is None:
            limit = self.config.historical_limit

        params = {}
        if limit > 0:
            params["limit"] = limit

        async with self._rate_limiter:
            try:
                start_time = time.time()
                response = await self._client.get(str(self.config.base_url), params=params)
                response.raise_for_status()

                data = response.json()
                self._last_fetch_time = time.time()

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    "fear_greed_data_fetched",
                    latency_ms=round(latency_ms, 2),
                    entries_count=len(data.get("data", [])),
                )

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "fear_greed_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error("fear_greed_request_error", error=str(e))
                raise

    async def get_latest(self) -> dict[str, Any]:
        """Fetch only the latest Fear & Greed Index value.

        Returns:
            Dictionary with current index data:
            - value: Index value (0-100)
            - value_classification: Sentiment label
            - timestamp: Unix timestamp
            - time_until_update: Seconds until next update
        """
        data = await self.get_index_data(limit=1)
        if data.get("data"):
            return data["data"][0]
        return {}

    async def get_historical(
        self,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Fetch historical Fear & Greed Index data.

        Args:
            days: Number of days of history to fetch

        Returns:
            List of historical index entries
        """
        data = await self.get_index_data(limit=days)
        return data.get("data", [])

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
            data = await self.get_index_data(limit=1)
            latency = (time.time() - start) * 1000

            if data.get("metadata", {}).get("error"):
                return {
                    "status": "degraded",
                    "latency_ms": round(latency, 2),
                    "message": f"API returned error: {data['metadata']['error']}",
                }

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
