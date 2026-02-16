"""
Hyperliquid Stats Data Client.

This module provides an async HTTP client for fetching data from stats-data.hyperliquid.xyz.
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


class StatsDataClient:
    """
    Async HTTP client for Hyperliquid stats data.

    Fetches leaderboard and vault data from the official stats endpoint.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the Stats Data client.

        Args:
            base_url: Stats data base URL
            timeout: Request timeout in seconds (default: 120 for large files)
        """
        self.base_url = base_url or settings.stats_data_url
        self.timeout = timeout or 120.0  # Longer timeout for large files (25MB+)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "StatsDataClient":
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
        wait=wait_exponential(multiplier=2, min=5, max=60),
    )
    async def _fetch(self, endpoint: str) -> Any:
        """
        Fetch data from a stats endpoint.

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
        logger.info(f"Fetching from Stats: {url}")

        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Data Endpoints
    # =========================================================================

    async def get_leaderboard(self) -> Dict:
        """
        Get the full leaderboard with all traders.

        Returns:
            Dictionary with leaderboardRows containing all traders
        """
        return await self._fetch("Mainnet/leaderboard")

    async def get_vaults(self) -> List[Dict]:
        """
        Get all vaults with their performance.

        Returns:
            List of vault dictionaries
        """
        return await self._fetch("Mainnet/vaults")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def extract_trader_info(trader_data: Dict) -> Dict:
        """
        Extract relevant trader information from leaderboard entry.

        Args:
            trader_data: Raw trader data from leaderboard

        Returns:
            Dictionary with extracted trader info
        """
        # Parse window performances
        performances = {}
        for window_data in trader_data.get("windowPerformances", []):
            window = window_data[0]  # day, week, month, allTime
            metrics = window_data[1]
            performances[window] = {
                "pnl": float(metrics.get("pnl", 0)),
                "roi": float(metrics.get("roi", 0)),
                "vlm": float(metrics.get("vlm", 0)),
            }

        return {
            "ethAddress": trader_data.get("ethAddress", ""),
            "accountValue": float(trader_data.get("accountValue", 0)),
            "displayName": trader_data.get("displayName"),
            "performances": performances,
        }

    @staticmethod
    def get_top_traders(
        leaderboard_data: Dict,
        limit: int = 500,
        min_account_value: float = 10000,
    ) -> List[Dict]:
        """
        Get top traders from leaderboard data.

        Args:
            leaderboard_data: Raw leaderboard response
            limit: Maximum number of traders to return
            min_account_value: Minimum account value filter

        Returns:
            List of trader dictionaries
        """
        rows = leaderboard_data.get("leaderboardRows", [])

        # Filter by account value
        filtered = [row for row in rows if float(row.get("accountValue", 0)) >= min_account_value]

        # Sort by account value
        sorted_traders = sorted(
            filtered,
            key=lambda x: float(x.get("accountValue", 0)),
            reverse=True,
        )

        # Limit results
        return sorted_traders[:limit]
