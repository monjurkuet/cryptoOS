# tests/unit/api/routes/test_signals.py

"""Tests for signal API routes."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.routes.signals import router


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
    app.include_router(router, prefix="/api/v1/signals")

    # Override the get_lifecycle dependency
    mock_lifecycle.repository = mock_repository
    app.state.lifecycle = mock_lifecycle

    return app


class TestListSignals:
    """Tests for list_signals endpoint."""

    @pytest.mark.asyncio
    async def test_list_signals_success(self, app, mock_repository) -> None:
        """Test successful list signals response."""
        mock_repository.get_signals.return_value = [
            {
                "t": datetime.now(UTC),
                "symbol": "BTC",
                "rec": "BUY",
                "conf": 0.85,
                "long_bias": 0.6,
                "short_bias": 0.2,
                "net_exp": 0.4,
                "t_long": 10,
                "t_short": 3,
                "t_flat": 2,
                "price": 50000,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        assert len(data["signals"]) == 1
        assert data["signals"][0]["recommendation"] == "BUY"
        assert data["signals"][0]["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_list_signals_with_filters(self, app, mock_repository) -> None:
        """Test list signals with filters."""
        mock_repository.get_signals.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/signals", params={"hours": 48, "limit": 50, "recommendation": "BUY"}
            )

        assert response.status_code == 200
        mock_repository.get_signals.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_signals_no_repository(self, app, mock_lifecycle) -> None:
        """Test list signals when repository is not available."""
        mock_lifecycle.repository = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals")

        assert response.status_code == 503


class TestGetCurrentSignal:
    """Tests for get_current_signal endpoint."""

    @pytest.mark.asyncio
    async def test_get_current_signal_success(self, app, mock_repository) -> None:
        """Test successful get current signal response."""
        mock_repository.get_current_signal.return_value = {
            "t": datetime.now(UTC),
            "symbol": "BTC",
            "rec": "BUY",
            "conf": 0.85,
            "long_bias": 0.6,
            "short_bias": 0.2,
            "net_exp": 0.4,
            "t_long": 10,
            "t_short": 3,
            "t_flat": 2,
            "price": 50000,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/current")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        assert data["recommendation"] == "BUY"
        assert data["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_get_current_signal_no_data(self, app, mock_repository) -> None:
        """Test get current signal when no data available."""
        mock_repository.get_current_signal.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/current")

        assert response.status_code == 200
        data = response.json()
        assert data["recommendation"] == "NEUTRAL"
        assert data["confidence"] == 0
        assert data["timestamp"] is None


class TestGetSignalStats:
    """Tests for get_signal_stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_signal_stats_success(self, app, mock_repository) -> None:
        """Test successful get signal stats response."""
        mock_repository.get_signal_stats.return_value = {
            "total": 100,
            "buy": 60,
            "sell": 25,
            "neutral": 15,
            "avg_confidence": 0.75,
            "avg_long_bias": 0.55,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/stats", params={"hours": 24})

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BTC"
        assert data["total_signals"] == 100
        assert data["buy_signals"] == 60
        assert data["sell_signals"] == 25
        assert data["neutral_signals"] == 15
        assert data["avg_confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_get_signal_stats_no_data(self, app, mock_repository) -> None:
        """Test get signal stats when no data available."""
        mock_repository.get_signal_stats.return_value = {
            "total": 0,
            "buy": 0,
            "sell": 0,
            "neutral": 0,
            "avg_confidence": 0.0,
            "avg_long_bias": 0.0,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_signals"] == 0


class TestGetSignal:
    """Tests for get_signal endpoint."""

    @pytest.mark.asyncio
    async def test_get_signal_not_found(self, app, mock_repository) -> None:
        """Test get signal when signal not found."""
        mock_repository.get_signal_by_id.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/signals/507f1f77bcf86cd799439011")

        assert response.status_code == 404
