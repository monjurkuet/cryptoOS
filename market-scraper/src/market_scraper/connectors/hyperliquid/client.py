# src/market_scraper/connectors/hyperliquid/client.py

"""Hyperliquid API client."""

import asyncio
from typing import Any

import httpx

from market_scraper.core.exceptions import DataFetchError


class HyperliquidClient:
    """HTTP client for Hyperliquid API."""

    def __init__(
        self,
        base_url: str = "https://api.hyperliquid.xyz",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._client: httpx.AsyncClient | None = None
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time: float | None = None

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        """Make a request with rate limiting and retries.

        Args:
            method: HTTP method
            endpoint: API endpoint
            json_data: JSON payload

        Returns:
            Response JSON

        Raises:
            DataFetchError: If request fails after all retries
        """
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        for attempt in range(self._max_retries):
            try:
                async with self._rate_limit_lock:
                    # Apply rate limiting
                    if self._last_request_time is not None:
                        elapsed = asyncio.get_event_loop().time() - self._last_request_time
                        if elapsed < 0.1:  # Max 10 requests per second
                            await asyncio.sleep(0.1 - elapsed)

                    response = await self._client.request(
                        method=method,
                        url=endpoint,
                        json=json_data,
                    )
                    self._last_request_time = asyncio.get_event_loop().time()

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if attempt == self._max_retries - 1:
                    raise DataFetchError(
                        f"HTTP error {e.response.status_code}: {e.response.text}"
                    ) from e
                await asyncio.sleep(self._retry_delay * (attempt + 1))

            except httpx.RequestError as e:
                if attempt == self._max_retries - 1:
                    raise DataFetchError(f"Request failed: {e}") from e
                await asyncio.sleep(self._retry_delay * (attempt + 1))

        raise DataFetchError("Request failed after all retries")

    async def get_candles(
        self,
        coin: str,
        interval: str,
        start_time: int,
        end_time: int,
    ) -> list[dict]:
        """Fetch candle data for a coin.

        Args:
            coin: Coin symbol (e.g., "BTC")
            interval: Candle interval string (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            start_time: Start time in milliseconds
            end_time: End time in milliseconds

        Returns:
            List of candle data dictionaries
        """
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": coin,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
            },
        }
        return await self._request("POST", "/info", payload)

    async def get_meta(self) -> dict:
        """Get exchange metadata.

        Returns:
            Exchange metadata dictionary
        """
        payload = {"type": "meta"}
        return await self._request("POST", "/info", payload)

    async def get_all_mids(self) -> dict:
        """Get all mid prices.

        Returns:
            Dictionary of coin to mid price
        """
        payload = {"type": "allMids"}
        return await self._request("POST", "/info", payload)

    @staticmethod
    def _timeframe_to_seconds(timeframe: str) -> int:
        """Convert timeframe string to seconds.

        Args:
            timeframe: Timeframe string (e.g., "1m", "1h")

        Returns:
            Seconds
        """
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
        }
        return mapping.get(timeframe, 60)
