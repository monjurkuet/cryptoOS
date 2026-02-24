"""Tests for TraderWebSocketCollector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from market_scraper.connectors.hyperliquid.collectors.trader_ws import (
    TraderWebSocketCollector,
    TraderWSClient,
)
from market_scraper.config.market_config import BufferConfig
from market_scraper.core.config import HyperliquidSettings


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock event bus."""
    bus = MagicMock()
    bus.publish_bulk = AsyncMock()
    return bus


@pytest.fixture
def mock_config() -> HyperliquidSettings:
    """Create test configuration."""
    return HyperliquidSettings(
        symbol="BTC",
        ws_url="wss://api.hyperliquid.xyz/ws",
        heartbeat_interval=30,
        reconnect_max_attempts=5,
        reconnect_base_delay=1.0,
        reconnect_max_delay=60.0,
        position_max_interval=300,
    )


@pytest.fixture
def buffer_config() -> BufferConfig:
    """Create buffer configuration."""
    return BufferConfig(
        flush_interval=1.0,
        max_size=10,
    )


class TestTraderWebSocketCollector:
    """Tests for TraderWebSocketCollector."""

    def test_init(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        buffer_config: BufferConfig,
    ) -> None:
        """Test initialization."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            buffer_config=buffer_config,
        )

        assert collector.event_bus == mock_event_bus
        assert collector.config == mock_config
        assert collector._running is False
        assert collector._tracked_traders == []

    def test_get_stats(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        buffer_config: BufferConfig,
    ) -> None:
        """Test getting stats."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            buffer_config=buffer_config,
        )

        stats = collector.get_stats()

        assert "running" in stats
        assert "tracked_traders" in stats
        assert "messages_received" in stats
        assert stats["running"] is False

    def test_normalize_positions(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test position normalization."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        positions = [
            {"position": {"coin": "BTC", "szi": 1.5}},
            {"position": {"coin": "ETH", "szi": -2.0}},
        ]

        normalized = collector._normalize_positions(positions)

        assert "BTC:1.5" in normalized
        assert "ETH:-2.0" in normalized

    def test_normalize_positions_empty(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test normalization with empty positions."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        assert collector._normalize_positions([]) == ""
        assert collector._normalize_positions(None) == ""

    def test_has_significant_change_new_trader(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test significant change detection for new trader."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        positions = [{"position": {"coin": "BTC", "szi": 1.0}}]

        # New trader should be significant
        assert collector._has_significant_change("new_address", positions) is True

    def test_has_significant_change_same_position(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test significant change detection with same position."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        address = "test_address"
        positions = [{"position": {"coin": "BTC", "szi": 1.0}}]

        # First save
        collector._last_positions[address] = {
            "positions": positions,
            "normalized": collector._normalize_positions(positions),
            "timestamp": time.time(),
        }

        # Same position should not be significant
        assert collector._has_significant_change(address, positions) is False

    def test_has_significant_change_time_elapsed(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test significant change after time elapsed."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        address = "test_address"
        positions = [{"position": {"coin": "BTC", "szi": 1.0}}]

        # Set old timestamp
        collector._last_positions[address] = {
            "positions": positions,
            "normalized": collector._normalize_positions(positions),
            "timestamp": time.time() - 3600,  # 1 hour ago
        }

        # Should be significant due to time
        assert collector._has_significant_change(address, positions) is True

    def test_cleanup_stale_positions(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test cleanup of stale position entries."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        # Add stale entry
        collector._last_positions["stale_address"] = {
            "positions": [],
            "normalized": "",
            "timestamp": time.time() - 86400 - 1,  # Older than TTL
        }

        # Add fresh entry
        collector._last_positions["fresh_address"] = {
            "positions": [],
            "normalized": "",
            "timestamp": time.time(),
        }

        collector._cleanup_stale_positions()

        assert "stale_address" not in collector._last_positions
        assert "fresh_address" in collector._last_positions

    @pytest.mark.asyncio
    async def test_process_webdata2(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test processing webData2 message."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [
                        {
                            "position": {
                                "coin": "BTC",
                                "szi": 1.5,
                            }
                        }
                    ],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }

        event = collector._process_webdata2(msg)

        assert event is not None
        assert event.event_type == "trader_positions"
        assert event.payload["address"] == "test_address"
        assert event.payload["symbol"] == "BTC"

    @pytest.mark.asyncio
    async def test_process_webdata2_no_positions(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test processing webData2 with no positions."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [],
                },
            },
        }

        event = collector._process_webdata2(msg)
        assert event is None

    @pytest.mark.asyncio
    async def test_process_webdata2_wrong_symbol(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Test processing webData2 with wrong symbol."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [
                        {
                            "position": {
                                "coin": "ETH",  # Not BTC
                                "szi": 1.5,
                            }
                        }
                    ],
                },
            },
        }

        event = collector._process_webdata2(msg)
        assert event is None


class TestTraderWSClient:
    """Tests for TraderWSClient."""

    def test_init(self, mock_config: HyperliquidSettings) -> None:
        """Test initialization."""
        client = TraderWSClient(
            client_id=0,
            traders=["address1", "address2"],
            on_message=AsyncMock(),
            on_disconnect=AsyncMock(),
            config=mock_config,
        )

        assert client.client_id == 0
        assert len(client.traders) == 2
        assert client._running is False

    @property
    def is_connected(self, mock_config: HyperliquidSettings) -> None:
        """Test is_connected property."""
        client = TraderWSClient(
            client_id=0,
            traders=[],
            on_message=AsyncMock(),
            on_disconnect=AsyncMock(),
            config=mock_config,
        )

        assert client.is_connected is False
