# tests/unit/api/test_health.py

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_liveness_probe():
    """Test liveness endpoint returns 200."""
    from market_scraper import app

    app.state.lifecycle = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_probe():
    """Test readiness endpoint returns 200 when healthy."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.health_check = AsyncMock(return_value={"api": True, "connectors": True})

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "api" in data["checks"]
        assert "connectors" in data["checks"]


@pytest.mark.asyncio
async def test_readiness_probe_unhealthy():
    """Test readiness endpoint returns 503 when unhealthy."""
    mock_lifecycle = MagicMock()
    mock_lifecycle.health_check = AsyncMock(return_value={"api": False, "connectors": True})

    from market_scraper import app

    app.state.lifecycle = mock_lifecycle

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/ready")
        assert response.status_code == 503


@pytest.mark.asyncio
async def test_health_status():
    """Test detailed health status endpoint."""
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
        assert data["status"] == "healthy"
