# src/market_scraper/connectors/cbbi/client.py

"""HTTP client for CBBI API interactions."""

import asyncio
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.cbbi.config import CBBIConfig

logger = structlog.get_logger(__name__)

# CBBI API endpoint
CBBI_LATEST_URL = "https://colintalkscrypto.com/cbbi/data/latest.json"


class CBBIClient:
    """HTTP client for fetching CBBI data.

    This client handles all HTTP interactions with the CBBI API,
    including connection management, request retries, and response handling.

    CBBI (Colin Talks Crypto Bitcoin Bull Run Index) provides Bitcoin
    sentiment data that updates approximately once per day.

    Attributes:
        config: CBBI configuration
        _client: HTTP client (initialized on connect)
    """

    def __init__(self, config: CBBIConfig) -> None:
        """Initialize the CBBI client.

        Args:
            config: CBBI connector configuration
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
            logger.info("cbbi_client_connected")
        except Exception as e:
            logger.error("cbbi_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize CBBI client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool.

        Gracefully closes all connections and releases resources.
        """
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("cbbi_client_closed")

    async def get_index_data(self) -> dict[str, Any]:
        """Fetch current CBBI index data.

        Retrieves the current CBBI index value and all component metrics.

        Returns:
            Dictionary containing CBBI index data with the following structure:
            {
                "Price": {timestamp: value, ...},
                "CBBI": {timestamp: confidence_score, ...},
                "PiCycleTop": {timestamp: value, ...},
                ... (other component metrics)
            }

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        async with self._rate_limiter:
            try:
                start_time = time.time()
                response = await self._client.get(CBBI_LATEST_URL)
                response.raise_for_status()

                data = response.json()
                self._last_fetch_time = time.time()

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    "cbbi_data_fetched",
                    latency_ms=round(latency_ms, 2),
                    metrics_count=len(data),
                )

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "cbbi_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error("cbbi_request_error", error=str(e))
                raise

    async def get_historical_data(
        self,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical CBBI data.

        The CBBI API returns all historical data in a single response,
        so this method fetches the full dataset and filters by days.

        Args:
            days: Number of days of history to fetch (defaults to config value)

        Returns:
            List of historical data points, each containing:
            {
                "date": str,
                "index_value": float,
                "components": dict
            }

        Raises:
            httpx.HTTPError: If the API request fails
        """
        if days is None:
            days = self.config.historical_days

        # Fetch all data
        data = await self.get_index_data()

        # Extract historical data points
        cbbi_data = data.get("CBBI", {})
        if not cbbi_data:
            return []

        # Get timestamps within the requested range
        cutoff_time = time.time() - (days * 86400)
        historical = []

        for ts_str, value in cbbi_data.items():
            try:
                ts = int(ts_str)
                if ts >= cutoff_time:
                    historical.append({
                        "timestamp": ts,
                        "date": time.strftime("%Y-%m-%d", time.gmtime(ts)),
                        "index_value": value,
                        "components": self._extract_components_at_time(data, ts),
                    })
            except (ValueError, TypeError):
                continue

        # Sort by timestamp descending
        historical.sort(key=lambda x: x["timestamp"], reverse=True)
        return historical

    async def get_component_data(self, component: str) -> dict[str, Any]:
        """Fetch data for a specific CBBI component.

        Args:
            component: Name of the component metric (e.g., "PiCycleTop",
                      "RUPL", "RHODL", "Puell", "TwoYearMA", "MVRV",
                      "ReserveRisk", "Woobull")

        Returns:
            Dictionary containing component data:
            {
                "component_name": str,
                "current_value": float,
                "historical": list,
            }

        Raises:
            ValueError: If component name is not found
            httpx.HTTPError: If the API request fails
        """
        data = await self.get_index_data()

        if component not in data:
            raise ValueError(f"Unknown component: {component}")

        component_data = data[component]
        if not component_data:
            return {"component_name": component, "current_value": None, "historical": []}

        # Get latest value
        timestamps = sorted(component_data.keys(), key=int, reverse=True)
        current_value = component_data.get(timestamps[0]) if timestamps else None

        # Build historical list
        historical = []
        for ts_str, value in component_data.items():
            try:
                historical.append({
                    "timestamp": int(ts_str),
                    "value": value,
                })
            except (ValueError, TypeError):
                continue

        historical.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "component_name": component,
            "current_value": current_value,
            "historical": historical,
        }

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
            await self.get_index_data()
            latency = (time.time() - start) * 1000

            # CBBI is "degraded" if we haven't fetched in over 2 days
            # (data should update daily)
            time_since_fetch = time.time() - self._last_fetch_time
            if time_since_fetch > 172800:  # 2 days
                return {
                    "status": "degraded",
                    "latency_ms": round(latency, 2),
                    "message": f"Last fetch was {int(time_since_fetch / 3600)} hours ago",
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

    def _extract_components_at_time(
        self, data: dict[str, Any], timestamp: int
    ) -> dict[str, float]:
        """Extract all component values at a specific timestamp.

        Args:
            data: Full CBBI data dict
            timestamp: Unix timestamp to extract values for

        Returns:
            Dict of component name -> value
        """
        components = {}
        ts_str = str(timestamp)

        # CBBI API field names (actual names from API)
        component_names = [
            "PiCycle",
            "RUPL",
            "RHODL",
            "Puell",
            "2YMA",
            "MVRV",
            "ReserveRisk",
            "Woobull",
            "Trolololo",
            "Price",
        ]

        for name in component_names:
            if name in data and ts_str in data[name]:
                try:
                    components[name] = float(data[name][ts_str])
                except (ValueError, TypeError):
                    continue

        return components
