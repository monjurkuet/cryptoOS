# tests/integration/test_lifecycle_integration.py

"""Integration tests for the lifecycle manager."""

import pytest

from market_scraper.core.config import Settings, HyperliquidSettings
from market_scraper.orchestration.lifecycle import LifecycleManager


@pytest.fixture
def test_settings():
    """Create test settings with memory storage."""
    return Settings(
        hyperliquid=HyperliquidSettings(
            enabled=False,  # Disable actual WebSocket connection for tests
            symbol="BTC",
        )
    )


@pytest.mark.asyncio
async def test_lifecycle_manager_startup_shutdown(test_settings):
    """Test that lifecycle manager starts and stops cleanly."""
    manager = LifecycleManager(settings=test_settings)

    # Startup
    await manager.startup()

    # Verify components are initialized
    assert manager._event_bus is not None
    assert manager._repository is not None
    assert manager._started is True

    # Shutdown
    await manager.shutdown()

    # Verify components are cleaned up
    assert manager._event_bus is None
    assert manager._repository is None
    assert manager._started is False


@pytest.mark.asyncio
async def test_lifecycle_manager_health_check(test_settings):
    """Test health check returns correct status."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    health = await manager.health_check()

    assert health["api"] is True
    assert health["event_bus"] is True
    assert health["repository"] is True
    assert health["collectors"] is False  # Disabled in test settings

    await manager.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_manager_get_markets(test_settings):
    """Test get markets returns configured symbol."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    markets = await manager.get_markets()

    assert len(markets) == 1
    assert markets[0]["symbol"] == "BTC"
    assert markets[0]["status"] == "active"

    await manager.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_manager_list_connectors(test_settings):
    """Test list connectors returns empty when disabled."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    connectors = await manager.list_connectors()

    # No connectors when disabled
    assert len(connectors) == 0

    await manager.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_manager_detailed_health(test_settings):
    """Test detailed health returns all components."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    health = await manager.get_detailed_health()

    assert "api" in health
    assert "event_bus" in health
    assert "repository" in health
    assert "collectors" in health

    assert health["event_bus"]["status"] == "healthy"
    assert health["repository"]["status"] == "healthy"

    await manager.shutdown()


@pytest.mark.asyncio
async def test_lifecycle_manager_with_custom_symbol():
    """Test lifecycle manager with custom symbol configuration."""
    settings = Settings(
        hyperliquid=HyperliquidSettings(
            enabled=False,
            symbol="ETH",
        )
    )
    manager = LifecycleManager(settings=settings)
    await manager.startup()

    markets = await manager.get_markets()

    assert markets[0]["symbol"] == "ETH"

    await manager.shutdown()
