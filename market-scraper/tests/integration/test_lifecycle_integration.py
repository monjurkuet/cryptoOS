# tests/integration/test_lifecycle_integration.py

"""Integration tests for the lifecycle manager."""

import asyncio
import os

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.routes.traders import router as traders_router
from market_scraper.config.market_config import CandleBackfillConfig, MarketConfig, SchedulerConfig
from market_scraper.core.events import StandardEvent
from market_scraper.core.config import HyperliquidSettings, MongoConfig, RedisConfig, Settings
from market_scraper.orchestration.lifecycle import LifecycleManager
from market_scraper.storage.base import QueryFilter

TEST_MONGO_URL = os.environ.get("MONGO__URL", "mongodb://localhost:27017")


@pytest.fixture(autouse=True)
def disable_background_jobs(monkeypatch: pytest.MonkeyPatch):
    """Disable network/backfill and scheduler side effects during lifecycle tests."""
    monkeypatch.setattr(
        "market_scraper.orchestration.lifecycle.load_market_config",
        lambda: MarketConfig(
            candle_backfill=CandleBackfillConfig(enabled=False, run_on_startup=False),
            scheduler=SchedulerConfig(enabled=False),
        ),
    )


@pytest.fixture
def test_settings():
    """Create test settings with memory storage."""
    return Settings(
        redis=RedisConfig(url=""),
        mongo=MongoConfig(url=TEST_MONGO_URL),
        hyperliquid=HyperliquidSettings(
            enabled=False,  # Disable actual WebSocket connection for tests
            symbol="BTC",
        ),
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
        redis=RedisConfig(url=""),
        mongo=MongoConfig(url=TEST_MONGO_URL),
        hyperliquid=HyperliquidSettings(
            enabled=False,
            symbol="ETH",
        ),
    )
    manager = LifecycleManager(settings=settings)
    await manager.startup()

    markets = await manager.get_markets()

    assert markets[0]["symbol"] == "ETH"

    await manager.shutdown()


@pytest.mark.asyncio
async def test_get_trader_returns_latest_ingested_position(test_settings):
    """GET /traders/{address} returns latest current-state after trader_positions ingestion."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    try:
        repository = manager.repository
        event_bus = manager.event_bus
        assert repository is not None
        assert event_bus is not None

        address = "0x1234567890123456789012345678901234567890"
        await repository.upsert_tracked_trader_data(
            {
                "eth": address,
                "name": "tracked trader",
                "score": 88.0,
                "tags": ["whale"],
                "acct_val": 1_000_000,
                "active": True,
            }
        )

        first_event = StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_ws",
            payload={
                "address": address,
                "symbol": "BTC",
                "positions": [
                    {
                        "position": {
                            "coin": "BTC",
                            "szi": 1.0,
                            "entryPx": 50000,
                            "markPx": 50500,
                            "unrealizedPnl": 500,
                            "leverage": {"value": 2},
                        }
                    }
                ],
                "marginSummary": {"accountValue": 1_000_000},
            },
        )
        second_event = StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_ws",
            payload={
                "address": address,
                "symbol": "BTC",
                "positions": [
                    {
                        "position": {
                            "coin": "BTC",
                            "szi": 2.5,
                            "entryPx": 50000,
                            "markPx": 52000,
                            "unrealizedPnl": 5000,
                            "leverage": {"value": 3},
                        }
                    }
                ],
                "marginSummary": {"accountValue": 1_100_000},
            },
        )

        await event_bus.publish(first_event)
        await event_bus.publish(second_event)
        await asyncio.sleep(0.05)

        app = FastAPI()
        app.include_router(traders_router, prefix="/api/v1/traders")
        app.state.lifecycle = manager

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/traders/{address}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["coin"] == "BTC"
        assert data["positions"][0]["size"] == 2.5
        assert data["positions"][0]["mark_price"] == 52000.0
        assert data["positions"][0]["leverage"] == 3.0
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_trader_positions_are_materialized_but_not_kept_in_raw_events(test_settings):
    """Trader position events should update canonical collections without bloating raw events."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    try:
        repository = manager.repository
        event_bus = manager.event_bus
        assert repository is not None
        assert event_bus is not None

        address = "0x1234567890123456789012345678901234567890"
        event = StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_ws",
            payload={
                "address": address,
                "symbol": "BTC",
                "positions": [
                    {
                        "position": {
                            "coin": "BTC",
                            "szi": 1.0,
                            "entryPx": 50000,
                            "markPx": 50500,
                            "unrealizedPnl": 500,
                            "leverage": {"value": 2},
                        }
                    }
                ],
                "marginSummary": {"accountValue": 1_000_000},
            },
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.05)

        state = await repository.get_trader_current_state(address)
        history = await repository.get_trader_positions_history(
            address=address, start_time=event.timestamp
        )
        raw_events = await repository.query(QueryFilter(event_type="trader_positions"))

        assert state is not None
        assert len(history) == 1
        assert raw_events == []
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_trader_closed_trades_are_materialized_from_live_position_transitions(test_settings):
    """Open-to-flat BTC transitions should append a closed-trade ledger row."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    try:
        repository = manager.repository
        event_bus = manager.event_bus
        assert repository is not None
        assert event_bus is not None

        address = "0x1234567890123456789012345678901234567890"
        await repository.upsert_tracked_trader_data(
            {
                "eth": address,
                "name": "tracked trader",
                "score": 88.0,
                "tags": ["whale"],
                "acct_val": 1_000_000,
                "active": True,
            }
        )

        open_event = StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_ws",
            payload={
                "address": address,
                "symbol": "BTC",
                "positions": [
                    {
                        "position": {
                            "coin": "BTC",
                            "szi": 1.0,
                            "entryPx": 50000,
                            "markPx": 50500,
                            "unrealizedPnl": 500,
                            "leverage": {"value": 2},
                        }
                    }
                ],
                "openOrders": [],
                "marginSummary": {"accountValue": 1_000_000},
            },
        )
        close_event = StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_ws",
            payload={
                "address": address,
                "symbol": "BTC",
                "positions": [],
                "openOrders": [],
                "marginSummary": {"accountValue": 1_000_000},
            },
        )

        await event_bus.publish(open_event)
        await event_bus.publish(close_event)
        await asyncio.sleep(0.05)

        app = FastAPI()
        app.include_router(traders_router, prefix="/api/v1/traders")
        app.state.lifecycle = manager

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/traders/{address}/closed-trades")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["closed_trades"][0]["direction"] == "long"
        assert data["closed_trades"][0]["close_reason"] == "flat"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_trading_signal_remains_in_raw_events_and_signals_collection(test_settings):
    """Trading signals should still be kept in both audit and canonical signal storage."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    try:
        repository = manager.repository
        event_bus = manager.event_bus
        assert repository is not None
        assert event_bus is not None

        event = StandardEvent.create(
            event_type="trading_signal",
            source="signal_generation",
            payload={
                "symbol": "BTC",
                "recommendation": "BUY",
                "confidence": 0.82,
                "longBias": 0.71,
                "shortBias": 0.29,
                "netExposure": 1.5,
                "tradersLong": 12,
                "tradersShort": 3,
                "tradersFlat": 4,
                "price": 65000,
            },
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.05)

        raw_events = await repository.query(QueryFilter(event_type="trading_signal"))
        signal = await repository.get_current_signal("BTC")

        assert len(raw_events) == 1
        assert signal is not None
        assert signal["rec"] == "BUY"
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_live_ohlcv_events_are_materialized_without_raw_event_duplication(test_settings):
    """Live OHLCV events should be persisted to candle storage instead of raw events."""
    manager = LifecycleManager(settings=test_settings)
    await manager.startup()

    try:
        repository = manager.repository
        event_bus = manager.event_bus
        assert repository is not None
        assert event_bus is not None

        event = StandardEvent.create(
            event_type="ohlcv",
            source="hyperliquid",
            payload={
                "symbol": "BTC",
                "timestamp": "2026-01-01T12:00:00+00:00",
                "interval": "1h",
                "open": 60000,
                "high": 61000,
                "low": 59500,
                "close": 60500,
                "volume": 123.45,
            },
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.05)

        latest_candle = await repository.get_latest_candle("BTC", "1h")
        raw_events = await repository.query(QueryFilter(event_type="ohlcv"))

        assert latest_candle is not None
        assert latest_candle["c"] == 60500
        assert raw_events == []
    finally:
        await manager.shutdown()
