# tests/unit/connectors/test_bitview.py

"""Unit tests for Bitview connector behavior."""

import asyncio
from unittest.mock import AsyncMock

from market_scraper.connectors.bitview.client import BitviewClient
from market_scraper.connectors.bitview.config import BitviewConfig


def test_health_check_uses_supported_series_probe() -> None:
    """Health checks should probe a supported series endpoint."""
    client = BitviewClient(BitviewConfig(name="bitview"))
    client._client = object()
    client._fetch_metric = AsyncMock(return_value={"data": ["2026-04-05"]})  # type: ignore[method-assign]

    health = asyncio.run(client.health_check())

    assert health["status"] == "healthy"
    client._fetch_metric.assert_awaited_once_with("date")  # type: ignore[attr-defined]
