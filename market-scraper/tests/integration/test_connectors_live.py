# tests/integration/test_connectors_live.py

"""Live integration tests for connectors.

These tests make real API calls and are marked as slow.
Run with: pytest tests/integration/test_connectors_live.py -v --slow
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from market_scraper.connectors.hyperliquid.client import HyperliquidClient
from market_scraper.connectors.hyperliquid.config import HyperliquidConfig
from market_scraper.connectors.hyperliquid.connector import HyperliquidConnector

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class TestHyperliquidClientLive:
    """Live tests for HyperliquidClient."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_connect_and_close(self) -> None:
        """Test connection lifecycle."""
        client = HyperliquidClient()
        await client.connect()
        assert client._client is not None
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_get_meta_live(self) -> None:
        """Test fetching metadata from live API."""
        client = HyperliquidClient()
        await client.connect()

        try:
            meta = await client.get_meta()
            assert "universe" in meta
            assert len(meta["universe"]) > 0
            print(f"Available markets: {len(meta['universe'])}")
        finally:
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_get_all_mids_live(self) -> None:
        """Test fetching all mid prices from live API."""
        client = HyperliquidClient()
        await client.connect()

        try:
            mids = await client.get_all_mids()
            assert "BTC" in mids
            assert float(mids["BTC"]) > 0
            print(f"BTC price: {mids['BTC']}")
        finally:
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_get_candles_live(self) -> None:
        """Test fetching candles from live API."""
        client = HyperliquidClient()
        await client.connect()

        try:
            end = int(datetime.now(UTC).timestamp() * 1000)
            start = end - 3600000  # 1 hour ago

            candles = await client.get_candles("BTC", "1m", start, end)

            assert isinstance(candles, list)
            if candles:  # May be empty if market is closed
                assert "t" in candles[0]  # timestamp
                assert "o" in candles[0]  # open
                print(f"Retrieved {len(candles)} candles")
        finally:
            await client.close()


class TestHyperliquidConnectorLive:
    """Live tests for HyperliquidConnector."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_health_check_live(self) -> None:
        """Test health check against live API."""
        config = HyperliquidConfig(name="hyperliquid")
        connector = HyperliquidConnector(config)

        await connector.connect()
        try:
            health = await connector.health_check()
            assert health["status"] == "healthy"
            assert health["latency_ms"] > 0
            print(f"Health check: {health}")
        finally:
            await connector.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.timeout(15)
    async def test_get_historical_data_live(self) -> None:
        """Test fetching historical data from live API."""
        config = HyperliquidConfig(name="hyperliquid")
        connector = HyperliquidConnector(config)

        await connector.connect()
        try:
            end = datetime.now(UTC)
            start = end - timedelta(hours=1)

            events = await connector.get_historical_data("BTC", "1m", start, end)

            assert isinstance(events, list)
            if events:
                assert events[0].event_type.value == "ohlcv"
                assert events[0].source == "hyperliquid"
                print(f"Retrieved {len(events)} events")
        finally:
            await connector.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_stream_realtime_live(self) -> None:
        """Test WebSocket streaming from live API."""
        config = HyperliquidConfig(name="hyperliquid")
        connector = HyperliquidConnector(config)

        await connector.connect()
        try:
            events = []
            timeout = asyncio.Timeout(5)

            try:
                async with asyncio.timeout(5):
                    async for event in connector.stream_realtime(["BTC"]):
                        if event:
                            events.append(event)
                            if len(events) >= 3:
                                break
            except TimeoutError:
                pass  # Expected if no events received

            print(f"Received {len(events)} events via WebSocket")

        finally:
            await connector.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_async_context_manager_live(self) -> None:
        """Test async context manager with live API."""
        config = HyperliquidConfig(name="hyperliquid")

        async with HyperliquidConnector(config) as connector:
            assert connector.is_connected is True
            health = await connector.health_check()
            assert health["status"] == "healthy"

        assert connector.is_connected is False
