# src/market_scraper/connectors/coin_metrics/client.py

"""HTTP client for Coin Metrics Community API interactions."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from market_scraper.connectors.coin_metrics.config import CoinMetricsConfig

logger = structlog.get_logger(__name__)


class CoinMetricsClient:
    """HTTP client for fetching Coin Metrics data.

    This client handles all HTTP interactions with the Coin Metrics
    Community API, including connection management and response handling.

    The Community API provides free access to basic cryptocurrency metrics
    without requiring an API key.

    Attributes:
        config: Coin Metrics configuration
        _client: HTTP client (initialized on connect)
    """

    def __init__(self, config: CoinMetricsConfig) -> None:
        """Initialize the Coin Metrics client.

        Args:
            config: Coin Metrics connector configuration
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
            headers = {
                "Accept": "application/json",
                "User-Agent": "MarketScraper/1.0",
            }
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                headers=headers,
            )
            logger.info("coin_metrics_client_connected")
        except Exception as e:
            logger.error("coin_metrics_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize Coin Metrics client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool.

        Gracefully closes all connections and releases resources.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("coin_metrics_client_closed")

    async def get_asset_metrics(
        self,
        asset: str | None = None,
        metrics: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Fetch asset metrics from Coin Metrics.

        Args:
            asset: Asset symbol (e.g., 'btc', 'eth')
            metrics: List of metric IDs to fetch
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time

        Returns:
            Dictionary containing:
            - data: List of metric data points

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        if asset is None:
            asset = self.config.asset
        if metrics is None:
            metrics = self.config.metrics

        url = f"{self.config.base_url}/timeseries/asset-metrics"
        params = {
            "assets": asset,
            "metrics": ",".join(metrics),
        }

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        async with self._rate_limiter:
            try:
                start = time.time()
                response = await self._client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                self._last_fetch_time = time.time()

                latency_ms = (time.time() - start) * 1000
                logger.info(
                    "coin_metrics_data_fetched",
                    asset=asset,
                    latency_ms=round(latency_ms, 2),
                    metrics_count=len(metrics),
                    data_points=len(data.get("data", [])),
                )

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "coin_metrics_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error("coin_metrics_request_error", error=str(e))
                raise

    async def get_latest_metrics(
        self,
        asset: str | None = None,
        metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch the latest metrics for an asset.

        Args:
            asset: Asset symbol
            metrics: List of metrics to fetch

        Returns:
            Dictionary with latest metric values
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        yesterday = datetime.now(UTC).strftime("%Y-%m-%d")

        data = await self.get_asset_metrics(
            asset=asset,
            metrics=metrics,
            start_time=yesterday,
            end_time=today,
        )

        if data.get("data"):
            return data["data"][-1]
        return {}

    async def get_metric_history(
        self,
        metric: str,
        asset: str | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Fetch historical data for a single metric.

        Args:
            metric: Metric ID
            asset: Asset symbol
            days: Number of days of history

        Returns:
            List of historical data points
        """
        from datetime import timedelta

        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(days=days)

        data = await self.get_asset_metrics(
            asset=asset,
            metrics=[metric],
            start_time=start_time.strftime("%Y-%m-%d"),
            end_time=end_time.strftime("%Y-%m-%d"),
        )

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
            await self.get_latest_metrics()
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
