"""
CloudFront CDN Data Client.

This module provides an async HTTP client for fetching data from CloudFront CDN.
"""

from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings


class CloudFrontClient:
    """
    Async HTTP client for CloudFront CDN data.

    Fetches historical market data from ASXN-cached CloudFront endpoints.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the CloudFront client.

        Args:
            base_url: CloudFront base URL
            timeout: Request timeout in seconds (default: 60 for large files)
        """
        self.base_url = base_url or settings.cloudfront_base_url
        self.timeout = timeout or 60.0  # Longer timeout for large files
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CloudFrontClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
    )
    async def _fetch(self, endpoint: str) -> Any:
        """
        Fetch data from a CloudFront endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            JSON response data

        Raises:
            httpx.HTTPError: If request fails
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        url = f"{self.base_url}/{endpoint}"
        logger.info(f"Fetching from CloudFront: {url}")

        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Data Endpoints
    # =========================================================================

    async def get_open_interest(self) -> Dict:
        """
        Get historical open interest data by coin.

        Returns:
            Dictionary with chart_data containing OI by date and coin
        """
        return await self._fetch("open_interest")

    async def get_funding_rate(self) -> Dict:
        """
        Get historical funding rates by coin.

        Returns:
            Dictionary with chart_data containing funding by date and coin
        """
        return await self._fetch("funding_rate")

    async def get_liquidity_by_coin(self) -> Dict:
        """
        Get liquidity metrics by coin.

        Returns:
            Dictionary with chart_data containing liquidity and slippage data
        """
        return await self._fetch("liquidity_by_coin")

    async def get_daily_liquidations(self) -> Dict:
        """
        Get daily liquidation notional by coin.

        Returns:
            Dictionary with chart_data containing liquidation data
        """
        return await self._fetch("daily_notional_liquidated_by_coin")

    async def get_daily_volume(self) -> Dict:
        """
        Get daily USD volume.

        Returns:
            Dictionary with chart_data containing daily volume
        """
        return await self._fetch("daily_usd_volume")

    async def get_daily_inflow(self) -> Dict:
        """
        Get daily inflow/outflow data.

        Returns:
            Dictionary with chart_data containing daily inflow
        """
        return await self._fetch("daily_inflow")

    async def get_cumulative_inflow(self) -> Dict:
        """
        Get cumulative inflow data.

        Returns:
            Dictionary with chart_data containing cumulative inflow
        """
        return await self._fetch("cumulative_inflow")

    # =========================================================================
    # Filter Helpers
    # =========================================================================

    @staticmethod
    def filter_by_coin(data: Dict, coin: str = "BTC") -> List[Dict]:
        """
        Filter chart_data by coin.

        Args:
            data: Raw API response with chart_data
            coin: Coin ticker to filter for

        Returns:
            List of records for the specified coin
        """
        chart_data = data.get("chart_data", [])
        if isinstance(chart_data, list):
            return [d for d in chart_data if d.get("coin") == coin]
        return []

    @staticmethod
    def filter_btc(data: Dict) -> List[Dict]:
        """
        Filter chart_data for BTC.

        Args:
            data: Raw API response with chart_data

        Returns:
            List of BTC records
        """
        return CloudFrontClient.filter_by_coin(data, "BTC")

    @staticmethod
    def transform_oi_record(record: Dict) -> Dict:
        """
        Transform an open interest record for database storage.

        Args:
            record: Raw OI record from API

        Returns:
            Transformed record with proper field names
        """
        return {
            "date": record.get("time", "").split("T")[0],  # Extract date
            "openInterest": record.get("open_interest"),
        }

    @staticmethod
    def transform_liquidity_record(record: Dict) -> Dict:
        """
        Transform a liquidity record for database storage.

        Args:
            record: Raw liquidity record from API

        Returns:
            Transformed record with proper field names
        """
        return {
            "date": record.get("time", "").split("T")[0],
            "midPrice": record.get("mid_price"),
            "medianLiquidity": record.get("median_liquidity"),
            "slippage1k": record.get("median_slippage_1000"),
            "slippage3k": record.get("median_slippage_3000"),
            "slippage10k": record.get("median_slippage_10000"),
            "slippage30k": record.get("median_slippage_30000"),
            "slippage100k": record.get("median_slippage_100000"),
        }

    @staticmethod
    def transform_liquidation_record(record: Dict) -> Dict:
        """
        Transform a liquidation record for database storage.

        Args:
            record: Raw liquidation record from API

        Returns:
            Transformed record with proper field names
        """
        return {
            "date": record.get("time", "").split("T")[0],
            "notionalLiquidated": record.get("daily_notional_liquidated"),
        }
