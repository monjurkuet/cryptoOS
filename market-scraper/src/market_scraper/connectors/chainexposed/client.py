# src/market_scraper/connectors/chainexposed/client.py

"""HTTP client for ChainExposed.com data extraction.

ChainExposed embeds on-chain metrics as JavaScript arrays in HTML pages.
This client scrapes those pages and extracts the data.
"""

import asyncio
import re
import time
from typing import Any

import httpx
import structlog

from market_scraper.connectors.chainexposed.config import ChainExposedConfig, ChainExposedMetric

logger = structlog.get_logger(__name__)


class ChainExposedClient:
    """HTTP client for fetching ChainExposed data.

    ChainExposed.com provides free Bitcoin on-chain metrics by embedding
    Plotly chart data as JavaScript arrays in HTML pages. This client
    scrapes those pages and extracts the x (dates) and y (values) arrays.

    No API key required. No rate limits.
    """

    def __init__(self, config: ChainExposedConfig) -> None:
        """Initialize the ChainExposed client.

        Args:
            config: ChainExposed connector configuration
        """
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._rate_limiter = asyncio.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_times: dict[str, float] = {}

    async def connect(self) -> None:
        """Establish HTTP connection pool."""
        if self._client is not None:
            return

        try:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
                headers={
                    "Accept": "text/html",
                    "User-Agent": "Mozilla/5.0 (compatible; MarketScraper/1.0)",
                },
            )
            logger.info("chainexposed_client_connected")
        except Exception as e:
            logger.error("chainexposed_client_connect_failed", error=str(e))
            raise ConnectionError(f"Failed to initialize ChainExposed client: {e}") from e

    async def close(self) -> None:
        """Close HTTP connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("chainexposed_client_closed")

    async def get_metric_data(
        self,
        metric: str | ChainExposedMetric,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Fetch data for a specific metric.

        Args:
            metric: Metric name (e.g., "SOPR", "NUPL", "MVRV")
            use_cache: Whether to use cached data if available

        Returns:
            Dictionary containing:
            - metric_name: Name of the metric
            - dates: List of date strings
            - values: List of float values
            - trace_names: List of trace names (for multi-trace metrics)
            - all_traces: Dict of trace_name -> {dates, values}

        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If data cannot be parsed
        """
        metric_str = metric.value if isinstance(metric, ChainExposedMetric) else metric

        # Check cache
        if use_cache and metric_str in self._cache:
            cache_age = time.time() - self._cache_times.get(metric_str, 0)
            if cache_age < self.config.cache_ttl_seconds:
                logger.debug("chainexposed_cache_hit", metric=metric_str)
                return self._cache[metric_str]

        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        url = f"{self.config.base_url}/{metric_str}.html"

        async with self._rate_limiter:
            try:
                start_time = time.time()
                response = await self._client.get(url)
                response.raise_for_status()

                html_content = response.text
                latency_ms = (time.time() - start_time) * 1000

                # Parse the HTML to extract x and y arrays
                data = self._parse_html_data(html_content, metric_str)

                # Cache the result
                self._cache[metric_str] = data
                self._cache_times[metric_str] = time.time()

                logger.info(
                    "chainexposed_data_fetched",
                    metric=metric_str,
                    latency_ms=round(latency_ms, 2),
                    data_points=len(data.get("dates", [])),
                    traces=len(data.get("all_traces", {})),
                )

                return data

            except httpx.HTTPStatusError as e:
                logger.error(
                    "chainexposed_http_error",
                    metric=metric_str,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                raise
            except httpx.RequestError as e:
                logger.error("chainexposed_request_error", metric=metric_str, error=str(e))
                raise

    def _parse_html_data(self, html: str, metric_name: str) -> dict[str, Any]:
        """Parse HTML to extract Plotly data arrays.

        ChainExposed embeds data in Plotly traces like:
        {
          x: ["2012-01-01","2012-01-02",...],
          y: ["5.2948427773232","5.2048778918761",...],
          name: "Trace Name",
          ...
        }

        Args:
            html: Raw HTML content
            metric_name: Name of the metric for logging

        Returns:
            Parsed data dictionary
        """
        # Find all x arrays
        x_pattern = r'x:\s*\[(.*?)\]'
        y_pattern = r'y:\s*\[(.*?)\]'
        name_pattern = r'name:\s*["\']([^"\']+)["\']'

        # Extract raw arrays (need to handle the content carefully)
        # Use a more robust approach: find all trace objects

        # Pattern to match Plotly trace objects
        trace_pattern = r'\{[^{}]*x:\s*\[[^\]]*\][^{}]*y:\s*\[[^\]]*\][^{}]*\}'

        # Simpler approach: extract x and y arrays separately, then match by index
        x_matches = re.findall(r'x:\s*\[(.*?)\]', html, re.DOTALL)
        y_matches = re.findall(r'y:\s*\[(.*?)\]', html, re.DOTALL)
        name_matches = re.findall(r'name:\s*["\']([^"\']+)["\']', html)

        if not x_matches or not y_matches:
            raise ValueError(f"No data arrays found in {metric_name} HTML")

        # Parse the arrays
        all_traces = {}

        for i, (x_raw, y_raw) in enumerate(zip(x_matches, y_matches)):
            try:
                dates = self._parse_string_array(x_raw)
                values = self._parse_value_array(y_raw)

                if not dates or not values:
                    continue

                # Get trace name if available
                trace_name = name_matches[i] if i < len(name_matches) else f"trace_{i}"

                all_traces[trace_name] = {
                    "dates": dates,
                    "values": values,
                }
            except Exception as e:
                logger.warning(
                    "chainexposed_trace_parse_failed",
                    metric=metric_name,
                    trace_index=i,
                    error=str(e),
                )
                continue

        # Find the main trace (usually the first non-empty one or one with specific name)
        main_trace = self._find_main_trace(all_traces, metric_name)

        result = {
            "metric_name": metric_name,
            "dates": main_trace.get("dates", []),
            "values": main_trace.get("values", []),
            "trace_name": main_trace.get("trace_name", ""),
            "all_traces": all_traces,
        }

        return result

    def _parse_string_array(self, raw: str) -> list[str]:
        """Parse a JavaScript string array from raw content.

        Args:
            raw: Raw content like '"2012-01-01","2012-01-02",...'

        Returns:
            List of strings
        """
        # Remove whitespace and split by comma
        items = []
        # Match quoted strings
        for match in re.finditer(r'"([^"]*)"', raw):
            items.append(match.group(1))
        return items

    def _parse_value_array(self, raw: str) -> list[float | None]:
        """Parse a JavaScript value array from raw content.

        Args:
            raw: Raw content like '"5.2948427773232","null","1.23",...'

        Returns:
            List of floats (None for null values)
        """
        items = []
        for match in re.finditer(r'"([^"]*)"', raw):
            val = match.group(1)
            if val.lower() == "null":
                items.append(None)
            else:
                try:
                    items.append(float(val))
                except ValueError:
                    items.append(None)
        return items

    def _find_main_trace(
        self, all_traces: dict[str, dict], metric_name: str
    ) -> dict[str, Any]:
        """Find the main data trace from multiple traces.

        Some metrics have multiple traces (e.g., HODL Waves has multiple bands).
        This method finds the most relevant one.

        Args:
            all_traces: Dict of trace_name -> {dates, values}
            metric_name: Name of the metric

        Returns:
            The main trace data
        """
        if not all_traces:
            return {"dates": [], "values": []}

        # For single-trace metrics, return the first one
        if len(all_traces) == 1:
            name = list(all_traces.keys())[0]
            return {**all_traces[name], "trace_name": name}

        # Priority 1: Look for "7d MA" or moving average traces (most reliable)
        for name, data in all_traces.items():
            name_lower = name.lower()
            if "7d ma" in name_lower or "ma" in name_lower:
                # Ensure it's not a price trace
                if "price" not in name_lower:
                    return {**data, "trace_name": name}

        # Priority 2: For SOPR metrics, look for SOPR in name but not Price
        if "sopr" in metric_name.lower():
            for name, data in all_traces.items():
                name_lower = name.lower()
                if "sopr" in name_lower and "price" not in name_lower:
                    return {**data, "trace_name": name}

        # Priority 3: Try to find trace with name matching metric
        for name, data in all_traces.items():
            if metric_name.lower() in name.lower():
                return {**data, "trace_name": name}

        # Priority 4: Look for trace with values in expected range
        # SOPR ~1.0, NUPL ~0-0.75, MVRV ~1-3
        for name, data in all_traces.items():
            if "price" in name.lower() or "inflection" in name.lower():
                continue
            values = [v for v in data.get("values", []) if v is not None]
            if values:
                avg = sum(values[-30:]) / len(values[-30:]) if len(values) >= 30 else sum(values) / len(values)
                # Check if average is in expected range
                if metric_name.upper() in ["SOPR", "NUPL", "MVRV", "DORMANCY"]:
                    if 0 < avg < 10:  # Reasonable range for these metrics
                        return {**data, "trace_name": name}

        # Fallback: Look for trace with most non-null values (excluding Price)
        best_trace = None
        best_count = 0
        for name, data in all_traces.items():
            if "price" in name.lower():
                continue
            count = sum(1 for v in data.get("values", []) if v is not None)
            if count > best_count:
                best_count = count
                best_trace = {**data, "trace_name": name}

        return best_trace or {"dates": [], "values": []}

    async def get_latest_value(self, metric: str | ChainExposedMetric) -> dict[str, Any]:
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

        dates = data.get("dates", [])
        values = data.get("values", [])

        if not dates or not values:
            return {
                "metric_name": data.get("metric_name", str(metric)),
                "value": None,
                "date": None,
                "change_7d": None,
            }

        # Find latest non-null value
        latest_value = None
        latest_date = None
        for i in range(len(values) - 1, -1, -1):
            if values[i] is not None:
                latest_value = values[i]
                latest_date = dates[i]
                break

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
            "metric_name": data.get("metric_name", str(metric)),
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
            await self.get_metric_data(ChainExposedMetric.SOPR, use_cache=False)
            latency = (time.time() - start) * 1000

            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": "ChainExposed API responding",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": str(e),
            }
