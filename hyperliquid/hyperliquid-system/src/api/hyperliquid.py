"""
Hyperliquid REST API Client.

This module provides an async HTTP client for interacting with the Hyperliquid API.
"""

import asyncio
from datetime import datetime
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


class HyperliquidClient:
    """
    Async HTTP client for Hyperliquid REST API.

    Handles rate limiting, retries, and error handling for all API calls.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        """
        Initialize the Hyperliquid API client.

        Args:
            base_url: API base URL (defaults to settings)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url or settings.hyperliquid_api_url
        self.timeout = timeout or settings.api_timeout
        self.max_retries = max_retries or settings.api_retry_attempts
        self._client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(settings.api_rate_limit)

    async def __aenter__(self) -> "HyperliquidClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
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
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(self, payload: Dict[str, Any]) -> Any:
        """
        Make a POST request to the API with rate limiting and retries.

        Args:
            payload: Request payload

        Returns:
            API response data

        Raises:
            httpx.HTTPError: If request fails after retries
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        async with self._semaphore:
            logger.debug(f"API Request: {payload}")
            response = await self._client.post(self.base_url, json=payload)
            response.raise_for_status()
            return response.json()

    # =========================================================================
    # Market Data Endpoints
    # =========================================================================

    async def get_candles(
        self,
        coin: str,
        interval: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get OHLCV candles for a coin.

        Args:
            coin: Coin ticker (e.g., "BTC")
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds

        Returns:
            List of candle dictionaries
        """
        # Use candleSnapshot endpoint with nested req object
        payload: Dict[str, Any] = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
            },
        }
        if start_time:
            payload["req"]["startTime"] = start_time
        if end_time:
            payload["req"]["endTime"] = end_time

        return await self._request(payload)

    async def get_l2_book(self, coin: str) -> Dict:
        """
        Get full depth orderbook for a coin.

        Args:
            coin: Coin ticker (e.g., "BTC")

        Returns:
            Orderbook dictionary with bids and asks
        """
        payload = {"type": "l2Book", "coin": coin}
        return await self._request(payload)

    async def get_trades(self, coin: str) -> List[Dict]:
        """
        Get recent public trades for a coin.

        Args:
            coin: Coin ticker (e.g., "BTC")

        Returns:
            List of trade dictionaries
        """
        payload = {"type": "recentTrades", "coin": coin}
        return await self._request(payload)

    async def get_ticker(self, coin: str) -> Dict:
        """
        Get ticker information for a coin using metaAndAssetCtxs.

        Args:
            coin: Coin ticker (e.g., "BTC")

        Returns:
            Ticker dictionary
        """
        # Get meta and asset contexts
        data = await self.get_meta_and_asset_ctxs()

        # Find the coin index from universe
        if len(data) < 2:
            return {}

        universe = data[0].get("universe", [])
        asset_ctxs = data[1] if len(data) > 1 else []

        # Find coin index
        coin_index = None
        for i, asset in enumerate(universe):
            if asset.get("name") == coin:
                coin_index = i
                break

        if coin_index is None or coin_index >= len(asset_ctxs):
            return {}

        ctx = asset_ctxs[coin_index]
        meta = universe[coin_index]

        return {
            "coin": coin,
            "markPx": ctx.get("markPx"),
            "midPx": ctx.get("midPx"),
            "oraclePx": ctx.get("oraclePx"),
            "funding": ctx.get("funding"),
            "openInterest": ctx.get("openInterest"),
            "prevDayPx": ctx.get("prevDayPx"),
            "dayNtlVlm": ctx.get("dayNtlVlm"),
            "dayBaseVlm": ctx.get("dayBaseVlm"),
            "premium": ctx.get("premium"),
            "maxLeverage": meta.get("maxLeverage"),
        }

    async def get_funding_history(self, coin: str) -> List[Dict]:
        """
        Get historical funding rates for a coin.

        Args:
            coin: Coin ticker (e.g., "BTC")

        Returns:
            List of funding history dictionaries
        """
        payload = {"type": "fundingHistory", "coin": coin}
        return await self._request(payload)

    async def get_all_mids(self) -> Dict[str, str]:
        """
        Get mark prices for all coins.

        Returns:
            Dictionary mapping coin to mark price
        """
        payload = {"type": "allMids"}
        return await self._request(payload)

    async def get_meta_and_asset_ctxs(self) -> List[Dict]:
        """
        Get metadata about all perpetual markets.

        Returns:
            List of market metadata dictionaries
        """
        payload = {"type": "metaAndAssetCtxs"}
        return await self._request(payload)

    # =========================================================================
    # User-Specific Endpoints
    # =========================================================================

    async def get_clearinghouse_state(self, user: str) -> Dict:
        """
        Get complete clearinghouse state for a user.

        Args:
            user: User's Ethereum address (with 0x prefix)

        Returns:
            Clearinghouse state with positions, margin info, etc.
        """
        payload = {"type": "clearinghouseState", "user": user}
        return await self._request(payload)

    async def get_open_orders(self, user: str) -> List[Dict]:
        """
        Get all open orders for a user.

        Args:
            user: User's Ethereum address

        Returns:
            List of open order dictionaries
        """
        payload = {"type": "openOrders", "user": user}
        return await self._request(payload)

    async def get_historical_orders(self, user: str) -> List[Dict]:
        """
        Get historical orders for a user.

        Args:
            user: User's Ethereum address

        Returns:
            List of historical order dictionaries
        """
        payload = {"type": "historicalOrders", "user": user}
        return await self._request(payload)

    async def get_user_funding(self, user: str, start_time: Optional[int] = None) -> List[Dict]:
        """
        Get funding payments for a user.

        Args:
            user: User's Ethereum address
            start_time: Start timestamp in milliseconds

        Returns:
            List of funding payment dictionaries
        """
        payload: Dict[str, Any] = {"type": "userFunding", "user": user}
        if start_time:
            payload["startTime"] = start_time
        return await self._request(payload)

    async def get_fills(self, user: str) -> List[Dict]:
        """
        Get recent trade executions (fills) for a user.

        Args:
            user: User's Ethereum address

        Returns:
            List of fill dictionaries
        """
        payload = {"type": "fills", "user": user}
        return await self._request(payload)

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def get_multiple_clearinghouse_states(
        self, users: List[str], concurrency: int = 10
    ) -> Dict[str, Dict]:
        """
        Get clearinghouse states for multiple users concurrently.

        Args:
            users: List of user Ethereum addresses
            concurrency: Maximum concurrent requests

        Returns:
            Dictionary mapping user address to their state
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def fetch_state(user: str) -> None:
            async with semaphore:
                try:
                    state = await self.get_clearinghouse_state(user)
                    results[user] = state
                except Exception as e:
                    logger.warning(f"Failed to fetch state for {user}: {e}")
                    results[user] = {}

        await asyncio.gather(*[fetch_state(user) for user in users])
        return results

    async def get_multiple_open_orders(
        self, users: List[str], concurrency: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        Get open orders for multiple users concurrently.

        Args:
            users: List of user Ethereum addresses
            concurrency: Maximum concurrent requests

        Returns:
            Dictionary mapping user address to their orders
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}

        async def fetch_orders(user: str) -> None:
            async with semaphore:
                try:
                    orders = await self.get_open_orders(user)
                    results[user] = orders
                except Exception as e:
                    logger.warning(f"Failed to fetch orders for {user}: {e}")
                    results[user] = []

        await asyncio.gather(*[fetch_orders(user) for user in users])
        return results
