# tests/unit/connectors/test_fear_greed.py

"""Unit tests for Fear & Greed connector behavior."""

import asyncio

import httpx

from market_scraper.connectors.fear_greed.client import FearGreedClient
from market_scraper.connectors.fear_greed.config import FearGreedConfig


class _DummyClient:
    """Minimal async HTTP client stub."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def get(self, url: str, params: dict[str, object] | None = None) -> httpx.Response:
        """Capture the request and return a JSON response."""
        self.calls.append({"url": url, "params": params or {}})
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json=self.payload, request=request)


def test_default_base_url_has_trailing_slash() -> None:
    """The canonical Alternative.me endpoint includes a trailing slash."""
    config = FearGreedConfig(name="fear_greed")
    assert str(config.base_url) == "https://api.alternative.me/fng/"


def test_client_sends_limit_zero_for_full_history() -> None:
    """A zero limit should be forwarded to request full history."""
    payload = {
        "name": "Fear and Greed Index",
        "data": [
            {
                "value": "55",
                "value_classification": "Neutral",
                "timestamp": "1771372800",
            }
        ],
        "metadata": {"error": None},
    }
    client = FearGreedClient(FearGreedConfig(name="fear_greed"))
    client._client = _DummyClient(payload)

    asyncio.run(client.get_index_data(limit=0))

    call = client._client.calls[0]
    assert call["url"] == "https://api.alternative.me/fng/"
    assert call["params"] == {"limit": 0}
