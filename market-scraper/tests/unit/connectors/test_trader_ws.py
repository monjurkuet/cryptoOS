"""Tests for TraderWebSocketCollector."""

import asyncio
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_scraper.config.market_config import BufferConfig
from market_scraper.connectors.hyperliquid.collectors.trader_ws import (
    TraderWebSocketCollector,
    TraderWSClient,
)
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
        reversed_positions = list(reversed(positions))

        normalized = collector._normalize_positions(positions)
        reversed_normalized = collector._normalize_positions(reversed_positions)

        assert normalized == reversed_normalized
        assert '"coin":"BTC"' in normalized
        assert '"coin":"ETH"' in normalized

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
        changed, computed = collector._has_significant_change("new_address", positions)
        assert changed is True
        assert "normalized" in computed

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

        # First save - store hash like _create_trader_positions_event does
        normalized = collector._normalize_positions(positions)
        combined_hash = hashlib.sha256((normalized + "").encode()).hexdigest()
        collector._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time(),
        }

        # Same position should not be significant
        changed, computed = collector._has_significant_change(address, positions)
        assert changed is False

    def test_has_significant_change_same_size_different_mark_price(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Price and PnL updates should still be treated as a real change."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        address = "test_address"
        original_positions = [
            {"position": {"coin": "BTC", "szi": 1.0, "markPx": 50000, "unrealizedPnl": 100}}
        ]
        updated_positions = [
            {"position": {"coin": "BTC", "szi": 1.0, "markPx": 50500, "unrealizedPnl": 600}}
        ]

        normalized = collector._normalize_positions(original_positions)
        margin_str = collector._normalize_margin_summary({"accountValue": 100000})
        combined_hash = hashlib.sha256((normalized + "" + margin_str).encode()).hexdigest()
        collector._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time(),
        }

        changed, computed = collector._has_significant_change(
            address,
            updated_positions,
            [],
            {"accountValue": 100000},
        )
        assert changed is True

    def test_has_significant_change_margin_summary_update(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Margin summary changes should still be emitted for current-state accuracy."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        address = "test_address"
        positions = [{"position": {"coin": "BTC", "szi": 1.0}}]

        normalized = collector._normalize_positions(positions)
        margin_str = collector._normalize_margin_summary({"accountValue": 100000})
        combined_hash = hashlib.sha256((normalized + "" + margin_str).encode()).hexdigest()
        collector._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time(),
        }

        changed, computed = collector._has_significant_change(
            address,
            positions,
            [],
            {"accountValue": 125000},
        )
        assert changed is True

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
        normalized = collector._normalize_positions(positions)
        combined_hash = hashlib.sha256((normalized + "").encode()).hexdigest()
        collector._last_positions[address] = {
            "hash": combined_hash,
            "timestamp": time.time() - 3600,  # 1 hour ago
        }

        # Should be significant due to time
        changed, computed = collector._has_significant_change(address, positions)
        assert changed is True

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
            "hash": "",
            "timestamp": time.time() - 86400 - 1,
        }

        # Add fresh entry
        collector._last_positions["fresh_address"] = {
            "hash": "",
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
    async def test_process_webdata2_same_size_price_change_still_emits_event(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Same-size updates should still emit when the persisted state changed."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        first_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [
                        {
                            "position": {
                                "coin": "BTC",
                                "szi": 1.5,
                                "markPx": 50000,
                            }
                        }
                    ],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }
        second_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [
                        {
                            "position": {
                                "coin": "BTC",
                                "szi": 1.5,
                                "markPx": 50500,
                            }
                        }
                    ],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }

        assert collector._process_webdata2(first_msg) is not None
        assert collector._process_webdata2(second_msg) is not None

    @pytest.mark.asyncio
    async def test_process_webdata2_position_close_emits_flat_transition(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """A previously active BTC position should emit an empty snapshot on close."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        open_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [
                        {
                            "position": {
                                "coin": "BTC",
                                "szi": 1.0,
                            }
                        }
                    ],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }
        close_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "clearinghouseState": {
                    "assetPositions": [],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }

        assert collector._process_webdata2(open_msg) is not None
        close_event = collector._process_webdata2(close_msg)
        assert close_event is not None
        assert close_event.event_type == "trader_positions"
        assert close_event.payload["positions"] == []

    def test_create_trader_positions_event_allows_empty_when_requested(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Bootstrap-style reconciliation should emit empty snapshots for new traders."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        event = collector._create_trader_positions_event(
            address="test_address",
            symbol_positions=[],
            open_orders=[],
            margin_summary={},
            allow_empty=True,
        )
        assert event is not None
        assert event.event_type == "trader_positions"
        assert event.payload["positions"] == []
        assert event.payload["openOrders"] == []

    def test_filter_symbol_open_orders(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Only active BTC open orders should be included."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        orders = [
            {"coin": "BTC", "sz": "1.0", "oid": 1},
            {"coin": "BTC", "sz": "0", "oid": 2},
            {"coin": "ETH", "sz": "5.0", "oid": 3},
            {"coin": "BTC", "sz": "-1", "oid": 4},
        ]

        filtered = collector._filter_symbol_open_orders(orders)
        assert filtered == [{"coin": "BTC", "sz": "1.0", "oid": 1}]

    @pytest.mark.asyncio
    async def test_process_webdata2_includes_open_orders(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """webData2 should emit BTC open orders in event payload."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "openOrders": [
                    {"coin": "BTC", "sz": "0.5", "oid": 100},
                    {"coin": "ETH", "sz": "2.0", "oid": 200},
                ],
                "clearinghouseState": {
                    "assetPositions": [],
                    "marginSummary": {"accountValue": 100000},
                },
            },
        }

        event = collector._process_webdata2(msg)
        assert event is not None
        assert event.payload["openOrders"] == [{"coin": "BTC", "sz": "0.5", "oid": 100}]

    @pytest.mark.asyncio
    async def test_process_webdata2_order_only_change_emits_event(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Order-only updates should emit a new event."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        first_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "openOrders": [{"coin": "BTC", "sz": "0.5", "oid": 100}],
                "clearinghouseState": {"assetPositions": [], "marginSummary": {}},
            },
        }
        second_msg = {
            "channel": "webData2",
            "data": {
                "user": "test_address",
                "openOrders": [{"coin": "BTC", "sz": "0.7", "oid": 100}],
                "clearinghouseState": {"assetPositions": [], "marginSummary": {}},
            },
        }

        assert collector._process_webdata2(first_msg) is not None
        assert collector._process_webdata2(second_msg) is not None

    @pytest.mark.asyncio
    async def test_fetch_bootstrap_event_includes_open_orders(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
    ) -> None:
        """Bootstrap fetch should include BTC open orders in emitted payload."""
        collector = TraderWebSocketCollector(
            event_bus=mock_event_bus,
            config=mock_config,
        )

        class _MockResponse:
            def __init__(self, payload):
                self.status = 200
                self._payload = payload

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def json(self):
                return self._payload

        class _MockSession:
            def __init__(self):
                self._calls = 0

            def post(self, *_args, **_kwargs):
                self._calls += 1
                if self._calls == 1:
                    return _MockResponse(
                        {
                            "assetPositions": [
                                {"position": {"coin": "BTC", "szi": "1.0"}},
                            ],
                            "marginSummary": {"accountValue": "100000"},
                        }
                    )
                return _MockResponse(
                    [
                        {"coin": "BTC", "sz": "0.5", "oid": 10},
                        {"coin": "ETH", "sz": "2.0", "oid": 20},
                    ]
                )

        event = await collector._fetch_bootstrap_event(
            session=_MockSession(),
            sem=asyncio.Semaphore(1),
            address="0xabc",
        )

        assert event is not None
        assert event.payload["openOrders"] == [{"coin": "BTC", "sz": "0.5", "oid": 10}]

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
