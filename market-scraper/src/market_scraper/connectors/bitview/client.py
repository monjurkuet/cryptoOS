# src/market_scraper/connectors/bitview/client.py

"""HTTP client for Bitview.space API (Bitcoin Research Kit).

Bitview.space is a free, open-source Bitcoin on-chain analytics platform
that computes metrics directly from a Bitcoin node. No API key required.
"""

import asyncio
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.bitview.config import BitviewConfig, BitviewMetric

logger = structlog.get_logger(__name__)


class BitviewClient:
    """HTTP client for fetching Bitview data.

    Bitview.space provides free Bitcoin on-chain metrics computed from
    a live Bitcoin node. All data is computed locally without external
    dependencies.

    No API key required. No rate limits.

    API Documentation: https://bitview.space/api
    Open Source: https://github.com/bitcoinresearchkit/brk
    """

    def __init__(self, config: BitviewConfig) -> None:
        """Initialize the Bitview client.

        Args:
            config: Bitview connector configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = asyncio.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_times: dict[str, float] = {}
        self._dates: list[str] = []
        self._dates_loaded = False

    async def connect(self) -> None:
        """Establish HTTP connection pool."""
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
            logger.info("bitview_client_connected")

            # Pre-fetch dates for index mapping
            await self._load_dates()

        except Exception as e:
            logger.error("bitview_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize Bitview client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("bitview_client_closed")

    async def _load_dates(self) -> None:
        """Load the date index for mapping array positions to dates."""
        if self._dates_loaded:
            return

        try:
            dates_data = await self._fetch_metric("date")
            # API returns data in the 'data' field
            self._dates = dates_data.get("data", [])
            self._dates_loaded = True
            logger.info("bitview_dates_loaded", count=len(self._dates))
        except Exception as e:
            logger.warning("bitview_dates_load_failed", error=str(e))
            self._dates = []

    async def _fetch_metric(self, metric: str) -> dict[str, Any]:
        """Fetch a single metric from the API.

        Args:
            metric: Metric name (e.g., "sopr", "nupl", "mvrv")

        Returns:
            Dictionary with metric data
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        url = f"{self.config.base_url}/metric/{metric}/dateindex"

        async with self._rate_limiter:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.json()

    async def get_metric_data(
        self,
        metric: str | BitviewMetric,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch data for a specific metric.

        Args:
            metric: Metric name or enum
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing:
            - metric_name: Name of the metric
            - dates: List of date strings
            - values: List of float values
            - latest_value: Most recent non-null value
            - latest_date: Date of latest value

        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If data cannot be parsed
        """
        metric_str = metric.value if isinstance(metric, BitviewMetric) else metric

        # Check cache
        if use_cache and metric_str in self._cache:
            cache_age = time.time() - self._cache_times.get(metric_str, 0)
            if cache_age < self.config.cache_ttl_seconds:
                logger.debug("bitview_cache_hit", metric=metric_str)
                return self._cache[metric_str]

        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        # Ensure dates are loaded
        if not self._dates_loaded:
            await self._load_dates()

        try:
            start_time = time.time()

            # Fetch metric data
            raw_data = await self._fetch_metric(metric_str)

            # Parse the response
            values = raw_data.get("data", [])
            total = raw_data.get("total", 0)
            stamp = raw_data.get("stamp", "")

            # Use cached dates for date mapping
            dates = self._dates if self._dates_loaded else []

            # Find latest non-null value
            latest_value = None
            latest_index = -1
            for i in range(len(values) - 1, -1, -1):
                if values[i] is not None:
                    latest_value = values[i]
                    latest_index = i
                    break

            # Get the date for the latest value
            latest_date = dates[latest_index] if dates and latest_index < len(dates) else None

            # Build historical data
            historical = []
            for i, val in enumerate(values):
                if val is not None and i < len(dates):
                    historical.append({
                        "date": dates[i],
                        "value": val,
                    })

            # Keep only last 365 days
            historical = historical[-365:]

            # Calculate statistics
            valid_values = [v for v in values if v is not None]
            stats = {}
            if valid_values:
                stats = {
                    "count": len(valid_values),
                    "min": min(valid_values),
                    "max": max(valid_values),
                    "mean": sum(valid_values) / len(valid_values),
                }

            data = {
                "metric_name": metric_str,
                "dates": dates,
                "values": values,
                "latest_value": latest_value,
                "latest_date": latest_date,
                "historical": historical,
                "statistics": stats,
                "total_points": total,
                "api_stamp": stamp,
            }

            # Cache the result
            self._cache[metric_str] = data
            self._cache_times[metric_str] = time.time()

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                "bitview_metric_fetched",
                metric=metric_str,
                latency_ms=round(latency_ms, 2),
                total_points=total,
                latest_value=latest_value,
                latest_date=latest_date,
            )

            return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "bitview_http_error",
                metric=metric_str,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise
        except httpx.RequestError as e:
            logger.error("bitview_request_error", metric=metric_str, error=str(e))
            raise

    async def get_multiple_metrics(
        self,
        metrics: list[str | BitviewMetric],
    ) -> dict[str, dict[str, Any]]:
        """Fetch multiple metrics in parallel.

        Args:
            metrics: List of metric names or enums

        Returns:
            Dictionary mapping metric names to their data
        """
        results = {}
        tasks = {}

        for metric in metrics:
            metric_str = metric.value if isinstance(metric, BitviewMetric) else metric
            tasks[metric_str] = self.get_metric_data(metric)

        # Fetch all in parallel
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for (metric_str, _), response in zip(tasks.items(), responses, strict=False):
            if isinstance(response, Exception):
                logger.warning(
                    "bitview_metric_fetch_failed",
                    metric=metric_str,
                    error=str(response),
                )
                results[metric_str] = {}
            else:
                results[metric_str] = response

        return results

    async def get_latest_value(self, metric: str | BitviewMetric) -> dict[str, Any]:
        """Get the latest value for a metric.

        Args:
            metric: Metric name

        Returns:
            Dictionary with:
            - metric_name: Name of metric
            - value: Latest value
            - date: Date of latest value
            - change_7d: 7-day change (if available)
        """
        data = await self.get_metric_data(metric)

        latest_value = data.get("latest_value")
        latest_date = data.get("latest_date")
        values = data.get("values", [])

        # Calculate 7-day change
        change_7d = None
        if latest_value is not None and len(values) >= 7:
            # Find value from ~7 days ago
            for i in range(len(values) - 8, -1, -1):
                if values[i] is not None:
                    old_value = values[i]
                    if old_value != 0:
                        change_7d = (latest_value - old_value) / old_value
                    break

        return {
            "metric_name": data.get("metric_name"),
            "value": latest_value,
            "date": latest_date,
            "change_7d": change_7d,
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

            # Try to fetch a simple metric
            response = await self._client.get(f"{self.config.base_url}/health")
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": round(latency, 2),
                    "message": "Bitview API responding",
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency_ms": round(latency, 2),
                    "message": f"API returned status {response.status_code}",
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": str(e),
            }
