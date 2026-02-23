# tests/unit/api/test_markets.py

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_markets():
    """Test listing all markets."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.get_markets = AsyncMock(
        return_value=[
            {
                "symbol": "BTC-USD",
                "source": "hyperliquid",
                "last_price": 50000.0,
                "last_update": datetime.now(UTC),
            },
            {
                "symbol": "ETH-USD",
                "source": "hyperliquid",
                "last_price": 3000.0,
                "last_update": datetime.now(UTC),
            },
        ]
    )

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["symbol"] == "BTC-USD"


@pytest.mark.asyncio
async def test_get_market():
    """Test getting market data for a specific symbol."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.get_market_data = AsyncMock(
        return_value={
            "symbol": "BTC-USD",
            "latest_candle": {
                "t": datetime.now(UTC).isoformat(),
                "o": 49900.0,
                "h": 50100.0,
                "l": 49800.0,
                "c": 50000.0,
                "v": 150.5,
            },
        }
    )

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets/BTC-USD")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert data["latest_candle"]["c"] == 50000.0  # Close price = current price


@pytest.mark.asyncio
async def test_get_market_not_found():
    """Test getting data for non-existent market."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.get_market_data = AsyncMock(return_value=None)

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets/INVALID")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_market_history():
    """Test getting market history."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.get_market_history = AsyncMock(
        return_value=[
            {
                "t": datetime.now(UTC).isoformat(),
                "o": 50000.0,
                "h": 50100.0,
                "l": 49900.0,
                "c": 50050.0,
                "v": 100.0,
            }
        ]
    )

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/markets/BTC-USD/history?timeframe=1h&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC-USD"
        assert data["timeframe"] == "1h"
        assert "candles" in data
        assert data["count"] == 1


@pytest.mark.asyncio
async def test_get_market_history_with_params():
    """Test getting market history with time parameters."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.get_market_history = AsyncMock(return_value=[])

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/markets/BTC-USD/history?"
            "timeframe=15m&"
            "start_time=2024-01-01T00:00:00&"
            "end_time=2024-01-02T00:00:00&"
            "limit=100"
        )
        assert response.status_code == 200
        mock_lifecycle.get_market_history.assert_called_once()
