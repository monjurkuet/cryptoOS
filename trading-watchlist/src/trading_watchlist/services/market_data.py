"""Market data helpers."""

import httpx


class MarketDataService:
    """Fetches live market data when needed."""

    def __init__(self, btc_market_url: str) -> None:
        self._btc_market_url = btc_market_url

    async def fetch_btc_price(self) -> float:
        """Fetch BTC price from local market API."""

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(self._btc_market_url)
            response.raise_for_status()
            payload = response.json()

        for key in ("price", "last_price", "lastPrice", "mark_price", "markPrice"):
            value = payload.get(key)
            if isinstance(value, int | float):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.replace(",", ""))
                except ValueError:
                    continue

        if isinstance(payload.get("data"), dict):
            nested = payload["data"]
            for key in ("price", "last_price", "lastPrice", "mark_price", "markPrice"):
                value = nested.get(key)
                if isinstance(value, int | float):
                    return float(value)
                if isinstance(value, str):
                    return float(value.replace(",", ""))

        raise ValueError("BTC price not found in market response")
