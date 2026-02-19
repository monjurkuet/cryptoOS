# tests/unit/connectors/test_hyperliquid.py

"""Unit tests for Hyperliquid connector."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from market_scraper.connectors.hyperliquid.client import HyperliquidClient
from market_scraper.connectors.hyperliquid.config import HyperliquidConfig
from market_scraper.connectors.hyperliquid.connector import HyperliquidConnector
from market_scraper.connectors.hyperliquid.parsers import (
    parse_candle,
    parse_orderbook,
    parse_ticker,
    parse_trade,
)
from market_scraper.core.events import EventType
from market_scraper.core.exceptions import DataFetchError


class TestHyperliquidConfig:
    """Test HyperliquidConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = HyperliquidConfig(name="hyperliquid")
        assert config.name == "hyperliquid"
        assert config.base_url == "https://api.hyperliquid.xyz"
        assert config.ws_url == "wss://api.hyperliquid.xyz/ws"
        assert config.api_key is None

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = HyperliquidConfig(
            name="hl_test",
            base_url="https://test.api.hyperliquid.xyz",
            ws_url="wss://test.api.hyperliquid.xyz/ws",
            api_key="test_key",
        )
        assert config.name == "hl_test"
        assert config.base_url == "https://test.api.hyperliquid.xyz"
        assert config.ws_url == "wss://test.api.hyperliquid.xyz/ws"
        assert config.api_key == "test_key"


class TestHyperliquidClient:
    """Test HyperliquidClient."""

    @pytest_asyncio.fixture
    async def client(self):
        """Create a client fixture."""
        client = HyperliquidClient()
        await client.connect()
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        """Test client connection."""
        client = HyperliquidClient()
        await client.connect()
        assert client._client is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test client closure."""
        client = HyperliquidClient()
        await client.connect()
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_candles(self, client) -> None:
        """Test fetching candles."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "t": 1704067200000,
                "o": "100.0",
                "h": "110.0",
                "l": "90.0",
                "c": "105.0",
                "v": "1000.0",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "request", return_value=mock_response):
            candles = await client.get_candles("BTC", "1m", 1704067200000, 1704153600000)

        assert len(candles) == 1
        assert candles[0]["t"] == 1704067200000

    @pytest.mark.asyncio
    async def test_get_meta(self, client) -> None:
        """Test fetching metadata."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"universe": [{"name": "BTC"}, {"name": "ETH"}]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "request", return_value=mock_response):
            meta = await client.get_meta()

        assert "universe" in meta
        assert len(meta["universe"]) == 2

    @pytest.mark.asyncio
    async def test_get_all_mids(self, client) -> None:
        """Test fetching all mids."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"BTC": "50000.0", "ETH": "3000.0"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "request", return_value=mock_response):
            mids = await client.get_all_mids()

        assert "BTC" in mids
        assert "ETH" in mids

    @pytest.mark.asyncio
    async def test_request_not_connected(self) -> None:
        """Test request when not connected raises error."""
        client = HyperliquidClient()
        with pytest.raises(RuntimeError, match="Client not connected"):
            await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_request_http_error(self, client) -> None:
        """Test request with HTTP error."""
        import httpx

        with patch.object(
            client._client,
            "request",
            side_effect=httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=500, text="Server Error"),
            ),
        ):
            with pytest.raises(DataFetchError, match="HTTP error 500"):
                await client._request("GET", "/test")


class TestParsers:
    """Test data parsers."""

    def test_parse_trade(self) -> None:
        """Test trade parser."""
        data = {
            "channel": "trades",
            "data": [{"coin": "BTC", "px": "50000.0", "sz": "1.5"}],
        }
        event = parse_trade(data, "hyperliquid")

        assert event is not None
        assert event.event_type == EventType.TRADE
        assert event.source == "hyperliquid"
        assert event.payload.symbol == "BTC"
        assert event.payload.price == 50000.0
        assert event.payload.volume == 1.5

    def test_parse_trade_empty(self) -> None:
        """Test trade parser with empty data."""
        data = {"channel": "trades", "data": []}
        event = parse_trade(data, "hyperliquid")
        assert event is None

    def test_parse_trade_invalid(self) -> None:
        """Test trade parser with invalid data."""
        data = {"channel": "trades", "data": [{"coin": "BTC", "px": "invalid", "sz": "invalid"}]}
        event = parse_trade(data, "hyperliquid")
        assert event is None

    def test_parse_orderbook(self) -> None:
        """Test orderbook parser."""
        data = {
            "channel": "l2Book",
            "data": {
                "coin": "BTC",
                "levels": [
                    [{"px": "49900.0", "sz": "2.0"}],
                    [{"px": "50100.0", "sz": "1.5"}],
                ],
            },
        }
        event = parse_orderbook(data, "hyperliquid")

        assert event is not None
        assert event.event_type == EventType.ORDER_BOOK
        assert event.source == "hyperliquid"
        assert event.payload.symbol == "BTC"
        assert event.payload.bid == 49900.0
        assert event.payload.ask == 50100.0

    def test_parse_orderbook_empty_levels(self) -> None:
        """Test orderbook parser with empty levels."""
        data = {"channel": "l2Book", "data": {"coin": "BTC", "levels": [[], []]}}
        event = parse_orderbook(data, "hyperliquid")

        assert event is not None
        assert event.payload.symbol == "BTC"
        assert event.payload.bid is None
        assert event.payload.ask is None

    def test_parse_ticker(self) -> None:
        """Test ticker parser."""
        data = {
            "channel": "ticker",
            "data": {"coin": "BTC", "markPrice": "50000.0"},
        }
        event = parse_ticker(data, "hyperliquid")

        assert event is not None
        assert event.event_type == EventType.TICKER
        assert event.source == "hyperliquid"
        assert event.payload.symbol == "BTC"
        assert event.payload.price == 50000.0

    def test_parse_candle(self) -> None:
        """Test candle parser."""
        data = {
            "t": 1704067200000,
            "o": "100.0",
            "h": "110.0",
            "l": "90.0",
            "c": "105.0",
            "v": "1000.0",
        }
        event = parse_candle(data, "hyperliquid", "BTC-USD")

        assert event is not None
        assert event.event_type == EventType.OHLCV
        assert event.source == "hyperliquid"
        assert event.payload.symbol == "BTC-USD"
        assert event.payload.open == 100.0
        assert event.payload.high == 110.0
        assert event.payload.low == 90.0
        assert event.payload.close == 105.0
        assert event.payload.volume == 1000.0


class TestHyperliquidConnector:
    """Test HyperliquidConnector."""

    @pytest.fixture
    def config(self) -> HyperliquidConfig:
        """Create test config."""
        return HyperliquidConfig(name="hyperliquid")

    @pytest_asyncio.fixture
    async def connector(self, config):
        """Create connected connector fixture."""
        with patch(
            "market_scraper.connectors.hyperliquid.connector.HyperliquidClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            conn = HyperliquidConnector(config)
            await conn.connect()
            yield conn
            await conn.disconnect()

    @pytest.mark.asyncio
    async def test_name_property(self, connector) -> None:
        """Test connector name."""
        assert connector.name == "hyperliquid"

    @pytest.mark.asyncio
    async def test_connect(self, config) -> None:
        """Test connection."""
        with patch(
            "market_scraper.connectors.hyperliquid.connector.HyperliquidClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            connector = HyperliquidConnector(config)
            await connector.connect()

            assert connector.is_connected is True
            assert connector._client is not None

            await connector.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect(self, connector) -> None:
        """Test disconnection."""
        await connector.disconnect()
        assert connector.is_connected is False

    @pytest.mark.asyncio
    async def test_get_historical_data(self, connector) -> None:
        """Test fetching historical data."""
        connector._client.get_candles.return_value = [
            {
                "t": 1704067200000,
                "o": "100.0",
                "h": "110.0",
                "l": "90.0",
                "c": "105.0",
                "v": "1000.0",
            }
        ]

        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 2, 0, 0, 0)

        events = await connector.get_historical_data("BTC", "1m", start, end)

        assert len(events) == 1
        assert events[0].event_type == EventType.OHLCV
        assert events[0].payload.symbol == "BTC"

        connector._client.get_candles.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_data_not_connected(self, config) -> None:
        """Test fetching data when not connected."""
        connector = HyperliquidConnector(config)

        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 2, 0, 0, 0)

        with pytest.raises(RuntimeError, match="Not connected"):
            await connector.get_historical_data("BTC", "1m", start, end)

    @pytest.mark.asyncio
    async def test_get_historical_data_unsupported_timeframe(self, connector) -> None:
        """Test fetching data with unsupported timeframe."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 2, 0, 0, 0)

        with pytest.raises(ValueError, match="Unsupported timeframe: 1s"):
            await connector.get_historical_data("BTC", "1s", start, end)

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, connector) -> None:
        """Test health check when healthy."""
        connector._client.get_meta.return_value = {"universe": [{"name": "BTC"}, {"name": "ETH"}]}

        health = await connector.health_check()

        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert "2 markets available" in health["message"]

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, connector) -> None:
        """Test health check when unhealthy."""
        connector._client.get_meta.side_effect = Exception("API Error")

        health = await connector.health_check()

        assert health["status"] == "unhealthy"
        assert health["latency_ms"] == 0
        assert "API Error" in health["message"]

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self, config) -> None:
        """Test health check when not connected."""
        connector = HyperliquidConnector(config)

        health = await connector.health_check()

        assert health["status"] == "unhealthy"
        assert "Client not connected" in health["message"]

    @pytest.mark.asyncio
    async def test_convert_timeframe(self, connector) -> None:
        """Test timeframe conversion."""
        assert connector._convert_timeframe("1m") == "1m"
        assert connector._convert_timeframe("5m") == "5m"
        assert connector._convert_timeframe("15m") == "15m"
        assert connector._convert_timeframe("1h") == "1h"
        assert connector._convert_timeframe("4h") == "4h"
        assert connector._convert_timeframe("1d") == "1d"

        with pytest.raises(ValueError, match="Unsupported timeframe: 1w"):
            connector._convert_timeframe("1w")

    def test_parse_websocket_message_trade(self, connector) -> None:
        """Test parsing trade WebSocket message."""
        data = {
            "channel": "trades",
            "data": [{"coin": "BTC", "px": "50000.0", "sz": "1.5"}],
        }
        event = connector._parse_websocket_message(data)

        assert event is not None
        assert event.event_type == EventType.TRADE

    def test_parse_websocket_message_orderbook(self, connector) -> None:
        """Test parsing orderbook WebSocket message."""
        data = {
            "channel": "l2Book",
            "data": {
                "coin": "BTC",
                "levels": [
                    [{"px": "49900.0", "sz": "2.0"}],
                    [{"px": "50100.0", "sz": "1.5"}],
                ],
            },
        }
        event = connector._parse_websocket_message(data)

        assert event is not None
        assert event.event_type == EventType.ORDER_BOOK

    def test_parse_websocket_message_ticker(self, connector) -> None:
        """Test parsing ticker WebSocket message."""
        data = {
            "channel": "ticker",
            "data": {"coin": "BTC", "markPrice": "50000.0"},
        }
        event = connector._parse_websocket_message(data)

        assert event is not None
        assert event.event_type == EventType.TICKER

    def test_parse_websocket_message_unknown(self, connector) -> None:
        """Test parsing unknown WebSocket message."""
        data = {"channel": "unknown", "data": {}}
        event = connector._parse_websocket_message(data)

        assert event is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self, config) -> None:
        """Test async context manager."""
        with patch(
            "market_scraper.connectors.hyperliquid.connector.HyperliquidClient"
        ) as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value = mock_instance

            async with HyperliquidConnector(config) as connector:
                assert connector.is_connected is True

            assert connector.is_connected is False
