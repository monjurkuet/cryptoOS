# tests/e2e/test_api.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Test health endpoints."""

    async def test_live_endpoint(self):
        """Test liveness probe."""
        from market_scraper import app

        app.state.lifecycle = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "alive"

    async def test_ready_endpoint(self):
        """Test readiness probe."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.health_check = AsyncMock(return_value={"api": True, "connectors": True})

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["ready"] is True

    async def test_status_endpoint(self):
        """Test detailed health status."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.get_detailed_health = AsyncMock(
            return_value={
                "api": {"status": "healthy"},
                "connectors": {"status": "healthy", "count": 0},
            }
        )

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health/status")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "version" in data
            assert "components" in data


@pytest.mark.asyncio
class TestMarketEndpoints:
    """Test market data endpoints."""

    async def test_list_markets(self):
        """Test listing markets."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.get_markets = AsyncMock(return_value=[])

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/markets")
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    async def test_get_market_not_found(self):
        """Test getting non-existent market."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.get_market_data = AsyncMock(return_value=None)

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/markets/INVALID")
            assert response.status_code == 404

    async def test_get_market_history(self):
        """Test getting market history."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.get_market_history = AsyncMock(return_value=[])

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/markets/BTC-USD/history")
            assert response.status_code == 200
            data = response.json()
            assert "symbol" in data
            assert "timeframe" in data
            assert "candles" in data


@pytest.mark.asyncio
class TestConnectorEndpoints:
    """Test connector management endpoints."""

    async def test_list_connectors(self):
        """Test listing connectors."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.list_connectors = AsyncMock(return_value=[])

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/connectors")
            assert response.status_code == 200
            assert isinstance(response.json(), list)

    async def test_get_connector_not_found(self):
        """Test getting non-existent connector."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.get_connector_status = AsyncMock(return_value=None)

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/v1/connectors/unknown")
            assert response.status_code == 404

    async def test_start_connector_not_found(self):
        """Test starting non-existent connector."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.start_connector = AsyncMock(side_effect=ValueError("Connector not found"))

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/v1/connectors/unknown/start")
            assert response.status_code == 404

    async def test_stop_connector_not_found(self):
        """Test stopping non-existent connector."""
        mock_lifecycle = MagicMock()
        mock_lifecycle.stop_connector = AsyncMock(side_effect=ValueError("Connector not found"))

        from market_scraper import app

        app.state.lifecycle = mock_lifecycle

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/v1/connectors/unknown/stop")
            assert response.status_code == 404


@pytest.mark.asyncio
class TestAPI:
    """General API tests."""

    async def test_openapi_docs_available(self):
        """Test OpenAPI documentation is available."""
        from market_scraper import app

        app.state.lifecycle = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/openapi.json")
            assert response.status_code == 200
            data = response.json()
            assert "info" in data
            assert data["info"]["title"] == "Market Scraper API"

    async def test_docs_available(self):
        """Test API docs page is available."""
        from market_scraper import app

        app.state.lifecycle = MagicMock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/docs")
            assert response.status_code == 200
