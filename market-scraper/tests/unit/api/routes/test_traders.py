# tests/unit/api/routes/test_traders.py

"""Tests for trader API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.routes.traders import router


@pytest.fixture
def mock_lifecycle():
    """Create a mock lifecycle manager."""
    lifecycle = MagicMock()
    lifecycle._settings = MagicMock()
    lifecycle._settings.hyperliquid = MagicMock()
    lifecycle._settings.hyperliquid.symbol = "BTC"
    return lifecycle


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def app(mock_lifecycle, mock_repository):
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/traders")

    # Override the get_lifecycle dependency
    mock_lifecycle.repository = mock_repository
    app.state.lifecycle = mock_lifecycle

    return app


class TestListTraders:
    """Tests for list_traders endpoint."""

    @pytest.mark.asyncio
    async def test_list_traders_success(self, app, mock_repository) -> None:
        """Test successful list traders response."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0x1234567890123456789012345678901234567890",
                "name": "Test Trader",
                "score": 75.5,
                "tags": ["whale"],
                "acct_val": 5000000,
                "active": True,
            }
        ]
        mock_repository.count_tracked_traders.return_value = 1

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["traders"]) == 1
        assert data["traders"][0]["address"] == "0x1234567890123456789012345678901234567890"
        assert data["traders"][0]["score"] == 75.5

    @pytest.mark.asyncio
    async def test_list_traders_with_filters(self, app, mock_repository) -> None:
        """Test list traders with min_score and tag filters."""
        mock_repository.get_tracked_traders.return_value = []
        mock_repository.count_tracked_traders.return_value = 0

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders", params={"min_score": 50, "tag": "whale"})

        assert response.status_code == 200
        mock_repository.get_tracked_traders.assert_called_once_with(
            min_score=50.0,
            tag="whale",
            active_only=True,
            limit=50,
        )

    @pytest.mark.asyncio
    async def test_list_traders_no_repository(self, app, mock_lifecycle) -> None:
        """Test list traders when repository is not available."""
        mock_lifecycle.repository = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders")

        assert response.status_code == 503
        assert "Repository not available" in response.json()["detail"]


class TestGetTrader:
    """Tests for get_trader endpoint."""

    @pytest.mark.asyncio
    async def test_get_trader_success(self, app, mock_repository) -> None:
        """Test successful get trader response."""
        mock_repository.get_trader_by_address.return_value = {
            "eth": "0x1234567890123456789012345678901234567890",
            "name": "Test Trader",
            "score": 75.5,
            "tags": ["whale"],
            "acct_val": 5000000,
            "active": True,
        }
        mock_repository.get_trader_current_state.return_value = {"positions": []}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["address"] == "0x1234567890123456789012345678901234567890"
        assert data["score"] == 75.5

    @pytest.mark.asyncio
    async def test_get_trader_not_found(self, app, mock_repository) -> None:
        """Test get trader when trader not found."""
        mock_repository.get_trader_by_address.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            )

        assert response.status_code == 404
        assert "Trader not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_trader_with_positions(self, app, mock_repository) -> None:
        """Test get trader with current positions."""
        mock_repository.get_trader_by_address.return_value = {
            "eth": "0x1234567890123456789012345678901234567890",
            "name": "Test Trader",
            "score": 75.5,
            "tags": [],
            "acct_val": 5000000,
            "active": True,
        }
        mock_repository.get_trader_current_state.return_value = {
            "positions": [
                {
                    "position": {
                        "coin": "BTC",
                        "szi": 1.5,
                        "entryPx": 50000,
                        "markPx": 55000,
                        "unrealizedPnl": 5000,
                        "leverage": {"value": 2},
                    }
                }
            ]
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["coin"] == "BTC"


class TestGetTraderPositions:
    """Tests for get_trader_positions endpoint."""

    @pytest.mark.asyncio
    async def test_get_positions_success(self, app, mock_repository) -> None:
        """Test successful get positions response."""
        mock_repository.get_trader_positions_history.return_value = [
            {
                "t": datetime.now(UTC),
                "coin": "BTC",
                "sz": 1.5,
                "ep": 50000,
                "mp": 55000,
                "upnl": 5000,
                "lev": 2,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/positions",
                params={"hours": 24},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["positions"]) == 1


class TestGetTraderSignals:
    """Tests for get_trader_signals endpoint."""

    @pytest.mark.asyncio
    async def test_get_signals_success(self, app, mock_repository) -> None:
        """Test successful get signals response."""
        mock_repository.get_trader_signals.return_value = [
            {
                "t": datetime.now(UTC),
                "symbol": "BTC",
                "action": "open",
                "dir": "long",
                "sz": 1.5,
                "conf": 0.85,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/signals",
                params={"hours": 24},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["signals"]) == 1
