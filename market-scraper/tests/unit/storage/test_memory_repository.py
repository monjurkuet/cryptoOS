"""Tests for the MemoryRepository implementation."""

from datetime import UTC, datetime, timedelta

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.storage.base import QueryFilter
from market_scraper.storage.memory_repository import MemoryRepository
from market_scraper.storage.models import Candle, TradingSignal


class TestMemoryRepository:
    """Test suite for MemoryRepository."""

    @pytest.fixture
    async def repository(self):
        """Create and connect a MemoryRepository."""
        repo = MemoryRepository()
        await repo.connect()
        yield repo
        await repo.disconnect()

    def create_trade_event(
        self,
        symbol: str = "BTC-USD",
        price: float = 50000.0,
        volume: float = 1.5,
        timestamp: datetime | None = None,
        source: str = "hyperliquid",
    ) -> StandardEvent:
        """Helper to create a trade event."""
        event_timestamp = timestamp or datetime.now(UTC)
        return StandardEvent.create(
            event_type=EventType.TRADE,
            source=source,
            payload=MarketDataPayload(
                symbol=symbol,
                price=price,
                volume=volume,
                timestamp=event_timestamp,
            ).model_dump(),
            timestamp=event_timestamp,
        )

    @staticmethod
    def create_live_position(
        size: float,
        entry_price: float = 50000.0,
        mark_price: float = 50500.0,
        unrealized_pnl: float = 0.0,
    ) -> list[dict]:
        """Build a live BTC position payload."""
        return [
            {
                "position": {
                    "coin": "BTC",
                    "szi": size,
                    "entryPx": entry_price,
                    "markPx": mark_price,
                    "unrealizedPnl": unrealized_pnl,
                    "leverage": {"value": 2},
                }
            }
        ]

    @pytest.mark.asyncio
    async def test_connect_disconnect(self):
        """Test connection lifecycle."""
        repo = MemoryRepository()
        assert not repo.is_connected

        await repo.connect()
        assert repo.is_connected

        await repo.disconnect()
        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with MemoryRepository() as repo:
            assert repo.is_connected

        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_store_single(self, repository: MemoryRepository):
        """Test storing a single event."""
        event = self.create_trade_event()

        result = await repository.store(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_store_not_connected(self):
        """Test storing when not connected raises error."""
        repo = MemoryRepository()
        event = self.create_trade_event()

        with pytest.raises(StorageError, match="not connected"):
            await repo.store(event)

    @pytest.mark.asyncio
    async def test_store_bulk(self, repository: MemoryRepository):
        """Test storing multiple events."""
        events = [self.create_trade_event(price=50000.0 + i, volume=1.0 + i) for i in range(10)]

        count = await repository.store_bulk(events)
        assert count == 10

    @pytest.mark.asyncio
    async def test_store_bulk_empty(self, repository: MemoryRepository):
        """Test storing empty list."""
        count = await repository.store_bulk([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_query_all(self, repository: MemoryRepository):
        """Test querying all events."""
        events = [
            self.create_trade_event(symbol="BTC-USD", price=50000.0),
            self.create_trade_event(symbol="ETH-USD", price=3000.0),
        ]
        await repository.store_bulk(events)

        results = await repository.query(QueryFilter())
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_by_symbol(self, repository: MemoryRepository):
        """Test filtering by symbol."""
        events = [
            self.create_trade_event(symbol="BTC-USD", price=50000.0),
            self.create_trade_event(symbol="ETH-USD", price=3000.0),
            self.create_trade_event(symbol="BTC-USD", price=51000.0),
        ]
        await repository.store_bulk(events)

        results = await repository.query(QueryFilter(symbol="BTC-USD"))
        assert len(results) == 2
        for r in results:
            # Payload can be dict or MarketDataPayload
            if isinstance(r.payload, dict):
                assert r.payload["symbol"] == "BTC-USD"
            else:
                from market_scraper.core.events import MarketDataPayload

                assert isinstance(r.payload, MarketDataPayload)
                assert r.payload.symbol == "BTC-USD"

    @pytest.mark.asyncio
    async def test_query_by_event_type(self, repository: MemoryRepository):
        """Test filtering by event type."""
        trade_event = self.create_trade_event()
        ticker_event = StandardEvent.create(
            event_type=EventType.TICKER,
            source="hyperliquid",
            payload=MarketDataPayload(
                symbol="BTC-USD",
                price=50000.0,
                timestamp=datetime.now(UTC),
            ).model_dump(),
        )
        await repository.store_bulk([trade_event, ticker_event])

        results = await repository.query(QueryFilter(event_type="trade"))
        assert len(results) == 1
        assert results[0].event_type == "trade"

    @pytest.mark.asyncio
    async def test_query_by_source(self, repository: MemoryRepository):
        """Test filtering by source."""
        events = [
            self.create_trade_event(source="hyperliquid"),
            self.create_trade_event(source="binance"),
            self.create_trade_event(source="hyperliquid"),
        ]
        await repository.store_bulk(events)

        results = await repository.query(QueryFilter(source="hyperliquid"))
        assert len(results) == 2
        for r in results:
            assert r.source == "hyperliquid"

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, repository: MemoryRepository):
        """Test filtering by time range."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)
        events = [
            self.create_trade_event(timestamp=base_time - timedelta(hours=2)),
            self.create_trade_event(timestamp=base_time),
            self.create_trade_event(timestamp=base_time + timedelta(hours=2)),
        ]
        await repository.store_bulk(events)

        # Query middle event only - use exact time range that includes the middle event
        results = await repository.query(
            QueryFilter(
                start_time=base_time,
                end_time=base_time,
            )
        )
        assert len(results) == 1
        assert results[0].timestamp == base_time

    @pytest.mark.asyncio
    async def test_query_limit_offset(self, repository: MemoryRepository):
        """Test limit and offset."""
        # Store events with different timestamps
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        events = [
            self.create_trade_event(timestamp=base_time + timedelta(minutes=i)) for i in range(10)
        ]
        await repository.store_bulk(events)

        # Test limit
        results = await repository.query(QueryFilter(limit=3))
        assert len(results) == 3

        # Test offset
        results = await repository.query(QueryFilter(limit=3, offset=3))
        assert len(results) == 3

        # Test combined
        results = await repository.query(QueryFilter(limit=2, offset=5))
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_latest(self, repository: MemoryRepository):
        """Test getting latest event."""
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        events = [
            self.create_trade_event(
                symbol="BTC-USD",
                timestamp=base_time + timedelta(minutes=i),
                price=50000.0 + i,
            )
            for i in range(5)
        ]
        await repository.store_bulk(events)

        latest = await repository.get_latest("BTC-USD", "trade")
        assert latest is not None
        # Payload can be dict or MarketDataPayload
        if isinstance(latest.payload, dict):
            assert latest.payload["price"] == 50004.0
        else:
            assert latest.payload.price == 50004.0

    @pytest.mark.asyncio
    async def test_get_latest_with_source(self, repository: MemoryRepository):
        """Test getting latest with source filter."""
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        events = [
            self.create_trade_event(
                symbol="BTC-USD",
                source="hyperliquid",
                timestamp=base_time + timedelta(minutes=1),
            ),
            self.create_trade_event(
                symbol="BTC-USD",
                source="binance",
                timestamp=base_time + timedelta(minutes=2),
            ),
        ]
        await repository.store_bulk(events)

        latest = await repository.get_latest("BTC-USD", "trade", source="hyperliquid")
        assert latest is not None
        assert latest.source == "hyperliquid"

    @pytest.mark.asyncio
    async def test_get_latest_not_found(self, repository: MemoryRepository):
        """Test getting latest when no events match."""
        latest = await repository.get_latest("BTC-USD", "trade")
        assert latest is None

    @pytest.mark.asyncio
    async def test_aggregate_ohlcv(self, repository: MemoryRepository):
        """Test OHLCV aggregation."""
        base_time = datetime(2024, 1, 1, 0, 0, 0)

        # Create trades across different 1-minute intervals
        trades = [
            # First minute
            self.create_trade_event(
                timestamp=base_time + timedelta(seconds=10),
                price=100.0,
                volume=1.0,
            ),
            self.create_trade_event(
                timestamp=base_time + timedelta(seconds=30),
                price=110.0,
                volume=2.0,
            ),
            self.create_trade_event(
                timestamp=base_time + timedelta(seconds=50),
                price=105.0,
                volume=1.5,
            ),
            # Second minute
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=1, seconds=10),
                price=120.0,
                volume=1.0,
            ),
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=1, seconds=30),
                price=125.0,
                volume=2.0,
            ),
        ]
        await repository.store_bulk(trades)

        results = await repository.aggregate_ohlcv(
            symbol="BTC-USD",
            timeframe="1m",
            start=base_time,
            end=base_time + timedelta(minutes=2),
        )

        assert len(results) == 2

        # Check first candle
        candle1 = results[0]
        assert candle1["open"] == 100.0
        assert candle1["high"] == 110.0
        assert candle1["low"] == 100.0
        assert candle1["close"] == 105.0
        assert candle1["volume"] == 4.5
        assert candle1["count"] == 3

        # Check second candle
        candle2 = results[1]
        assert candle2["open"] == 120.0
        assert candle2["high"] == 125.0
        assert candle2["low"] == 120.0
        assert candle2["close"] == 125.0
        assert candle2["volume"] == 3.0
        assert candle2["count"] == 2

    @pytest.mark.asyncio
    async def test_aggregate_ohlcv_hourly(self, repository: MemoryRepository):
        """Test OHLCV aggregation with hourly timeframe."""
        base_time = datetime(2024, 1, 1, 0, 0, 0)

        trades = [
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=10),
                price=100.0,
                volume=1.0,
            ),
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=30),
                price=110.0,
                volume=2.0,
            ),
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=50),
                price=105.0,
                volume=1.5,
            ),
        ]
        await repository.store_bulk(trades)

        results = await repository.aggregate_ohlcv(
            symbol="BTC-USD",
            timeframe="1h",
            start=base_time,
            end=base_time + timedelta(hours=1),
        )

        assert len(results) == 1
        assert results[0]["open"] == 100.0
        assert results[0]["high"] == 110.0
        assert results[0]["low"] == 100.0
        assert results[0]["close"] == 105.0
        assert results[0]["volume"] == 4.5

    @pytest.mark.asyncio
    async def test_aggregate_ohlcv_no_trades(self, repository: MemoryRepository):
        """Test OHLCV aggregation with no trades."""
        results = await repository.aggregate_ohlcv(
            symbol="BTC-USD",
            timeframe="1m",
            start=datetime(2024, 1, 1),
            end=datetime(2024, 1, 2),
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_aggregate_ohlcv_unsupported_timeframe(self, repository: MemoryRepository):
        """Test OHLCV aggregation with unsupported timeframe."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            await repository.aggregate_ohlcv(
                symbol="BTC-USD",
                timeframe="1y",  # Years not supported
                start=datetime(2024, 1, 1),
                end=datetime(2024, 1, 2),
            )

    @pytest.mark.asyncio
    async def test_health_check(self, repository: MemoryRepository):
        """Test health check."""
        health = await repository.health_check()

        assert health["status"] == "healthy"
        assert health["latency_ms"] == 0.0
        assert health["document_count"] == 0
        assert health["storage_size_mb"] == 0.0

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """Test health check when disconnected."""
        repo = MemoryRepository()
        health = await repo.health_check()

        assert health["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_clear(self, repository: MemoryRepository):
        """Test clearing all events."""
        events = [self.create_trade_event() for _ in range(5)]
        await repository.store_bulk(events)

        assert len(repository._events) == 5

        repository.clear()

        assert len(repository._events) == 0

    @pytest.mark.asyncio
    async def test_payload_as_marketdata(self, repository: MemoryRepository):
        """Test that MarketDataPayload objects work correctly."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=datetime.now(UTC),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload=payload,  # Pass as object, not dict
        )

        await repository.store(event)

        # Query should work with both dict and MarketDataPayload
        results = await repository.query(QueryFilter(symbol="BTC-USD"))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_tracked_traders_queries(self, repository: MemoryRepository):
        """Tracked trader queries return repository-backed data."""
        await repository.upsert_tracked_trader_data(
            {
                "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0001",
                "name": "alpha",
                "score": 91,
                "tags": ["whale"],
                "active": True,
            }
        )
        await repository.upsert_tracked_trader_data(
            {
                "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0002",
                "name": "beta",
                "score": 45,
                "tags": ["small"],
                "active": True,
            }
        )

        top = await repository.get_tracked_traders(min_score=50, tag="whale", active_only=True)
        assert len(top) == 1
        assert top[0]["eth"] == "0xabcdefabcdefabcdefabcdefabcdefabcdef0001"

        count = await repository.count_tracked_traders(min_score=40, active_only=True)
        assert count == 2

        fetched = await repository.get_trader_by_address(
            "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0001"
        )
        assert fetched is not None
        assert fetched["name"] == "alpha"

    @pytest.mark.asyncio
    async def test_upsert_tracked_trader_data_skips_unchanged_updates(
        self, repository: MemoryRepository
    ) -> None:
        """Unchanged tracked trader refreshes should not bump updated_at."""
        initial_time = datetime(2024, 1, 1, 12, 0, 0)
        later_time = datetime(2024, 1, 1, 13, 0, 0)
        trader = {
            "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0001",
            "name": "alpha",
            "score": 91,
            "tags": ["whale"],
            "active": True,
        }

        await repository.upsert_tracked_trader_data(trader, updated_at=initial_time)
        await repository.upsert_tracked_trader_data(trader, updated_at=later_time)

        assert (
            repository._tracked_traders["0xabcdefabcdefabcdefabcdefabcdefabcdef0001"]["updated_at"]
            == initial_time
        )

    @pytest.mark.asyncio
    async def test_trader_current_state_and_history(self, repository: MemoryRepository):
        """Current state and position history are persisted for traders."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003"
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.25}}],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )

        state = await repository.get_trader_current_state(address)
        assert state is not None
        assert state["eth"] == "0xabcdefabcdefabcdefabcdefabcdefabcdef0003"
        assert state["positions"][0]["position"]["coin"] == "BTC"

        await repository.store_trader_position(
            {
                "eth": address,
                "t": event_time,
                "coin": "BTC",
                "sz": 1.25,
                "ep": 50000,
                "mp": 51000,
                "upnl": 1250,
                "lev": 2,
            }
        )

        history = await repository.get_trader_positions_history(
            address=address,
            start_time=event_time.replace(hour=0),
        )
        assert len(history) == 1
        assert history[0]["coin"] == "BTC"

    @pytest.mark.asyncio
    async def test_get_trader_current_states_bulk_lookup(self, repository: MemoryRepository) -> None:
        """Bulk current-state lookup returns keyed states for matching addresses."""
        event_time = datetime(2024, 1, 1, 12, 0, 0)
        address_one = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0011"
        address_two = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0022"

        await repository.upsert_trader_current_state(
            address=address_one,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.0}}],
            open_orders=[{"coin": "BTC", "sz": "0.5", "oid": 1}],
            margin_summary={"accountValue": 1_000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address_two,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 2.0}}],
            open_orders=[],
            margin_summary={"accountValue": 2_000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )

        states = await repository.get_trader_current_states(
            [address_one.upper(), address_two.lower(), address_two.lower()],
            symbol="BTC",
        )

        assert set(states.keys()) == {address_one.lower(), address_two.lower()}
        assert states[address_one.lower()]["positions"][0]["position"]["szi"] == 1.0
        assert states[address_one.lower()]["open_orders"][0]["oid"] == 1
        assert states[address_two.lower()]["positions"][0]["position"]["szi"] == 2.0

    @pytest.mark.asyncio
    async def test_get_trader_current_states_respects_symbol_filter(
        self, repository: MemoryRepository
    ) -> None:
        """Bulk lookup can filter states by symbol."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0033"
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="ETH",
            positions=[{"position": {"coin": "ETH", "szi": 3.0}}],
            open_orders=[],
            margin_summary={"accountValue": 3_000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )

        btc_states = await repository.get_trader_current_states([address], symbol="BTC")
        eth_states = await repository.get_trader_current_states([address], symbol="ETH")

        assert btc_states == {}
        assert eth_states[address.lower()]["symbol"] == "ETH"

    @pytest.mark.asyncio
    async def test_get_trader_current_states_prefers_latest_state_per_address(
        self, repository: MemoryRepository
    ) -> None:
        """When symbol is not filtered, bulk lookup keeps the latest state by updated_at."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0044"
        older_time = datetime(2024, 1, 1, 12, 0, 0)
        newer_time = datetime(2024, 1, 1, 12, 5, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.0}}],
            open_orders=[],
            margin_summary={"accountValue": 4_000},
            event_timestamp=older_time,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="ETH",
            positions=[{"position": {"coin": "ETH", "szi": 2.0}}],
            open_orders=[],
            margin_summary={"accountValue": 5_000},
            event_timestamp=newer_time,
            source="hyperliquid_ws",
        )

        states = await repository.get_trader_current_states([address], symbol=None)
        assert states[address.lower()]["symbol"] == "ETH"

    @pytest.mark.asyncio
    async def test_trader_current_state_skips_unchanged_updates(
        self, repository: MemoryRepository
    ) -> None:
        """Current state writes are suppressed when the payload is unchanged."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003"
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.25}}],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )
        state_key = (address.lower(), "BTC")
        first_updated_at = repository._trader_current_state[state_key]["updated_at"]

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.25}}],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )

        assert repository._trader_current_state[state_key]["updated_at"] == first_updated_at

    @pytest.mark.asyncio
    async def test_trader_current_state_updates_when_open_orders_change(
        self, repository: MemoryRepository
    ) -> None:
        """Current state should refresh when open orders change."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0099"
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[],
            open_orders=[{"coin": "BTC", "sz": "0.5", "oid": 10}],
            margin_summary={"accountValue": 1000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )
        state_key = (address.lower(), "BTC")
        first_updated_at = repository._trader_current_state[state_key]["updated_at"]

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[],
            open_orders=[{"coin": "BTC", "sz": "0.75", "oid": 10}],
            margin_summary={"accountValue": 1000},
            event_timestamp=event_time,
            source="hyperliquid_ws",
        )

        assert repository._trader_current_state[state_key]["updated_at"] > first_updated_at

    @pytest.mark.asyncio
    async def test_trader_current_state_starts_trade_meta_without_closed_trade(
        self, repository: MemoryRepository
    ) -> None:
        """Flat to long should start trade metadata and keep closed-trade ledger empty."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0100"
        opened_at = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.0, mark_price=50600, unrealized_pnl=600),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at,
            source="hyperliquid_ws",
        )

        state = await repository.get_trader_current_state(address)
        closed_trades = await repository.get_trader_closed_trades(
            address=address,
            start_time=opened_at - timedelta(hours=1),
        )

        assert state is not None
        assert state["btc_trade_meta"]["direction"] == "long"
        assert state["btc_trade_meta"]["opened_at"] == opened_at
        assert state["btc_trade_meta"]["max_abs_size"] == 1.0
        assert closed_trades == []

    @pytest.mark.asyncio
    async def test_trader_current_state_updates_trade_meta_on_same_side_changes(
        self, repository: MemoryRepository
    ) -> None:
        """Same-side size changes should update trade metadata without closing the trade."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0101"
        opened_at = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.0, mark_price=50500, unrealized_pnl=500),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(2.5, mark_price=51000, unrealized_pnl=2500),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at + timedelta(minutes=5),
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.5, mark_price=50900, unrealized_pnl=1350),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at + timedelta(minutes=10),
            source="hyperliquid_ws",
        )

        state = await repository.get_trader_current_state(address)
        closed_trades = await repository.get_trader_closed_trades(
            address=address,
            start_time=opened_at - timedelta(hours=1),
        )

        assert state is not None
        assert state["btc_trade_meta"]["opened_at"] == opened_at
        assert state["btc_trade_meta"]["direction"] == "long"
        assert state["btc_trade_meta"]["max_abs_size"] == 2.5
        assert closed_trades == []

    @pytest.mark.asyncio
    async def test_trader_current_state_writes_closed_trade_on_flat(
        self, repository: MemoryRepository
    ) -> None:
        """Long to flat should append a closed trade and clear live trade metadata."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0102"
        opened_at = datetime(2024, 1, 1, 12, 0, 0)
        reduced_at = opened_at + timedelta(minutes=5)
        closed_at = opened_at + timedelta(minutes=10)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.0, mark_price=50500, unrealized_pnl=500),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(2.0, mark_price=52000, unrealized_pnl=4000),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=reduced_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.25, mark_price=51500, unrealized_pnl=1875),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=closed_at - timedelta(minutes=1),
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=closed_at,
            source="hyperliquid_ws",
        )

        state = await repository.get_trader_current_state(address)
        closed_trades = await repository.get_trader_closed_trades(
            address=address,
            start_time=opened_at - timedelta(hours=1),
        )

        assert state is not None
        assert state["positions"] == []
        assert state["btc_trade_meta"] == {}
        assert len(closed_trades) == 1
        assert closed_trades[0]["dir"] == "long"
        assert closed_trades[0]["opened_at"] == opened_at.replace(tzinfo=UTC)
        assert closed_trades[0]["closed_at"] == closed_at.replace(tzinfo=UTC)
        assert closed_trades[0]["max_abs_size"] == 2.0
        assert closed_trades[0]["final_abs_size"] == 1.25
        assert closed_trades[0]["close_reference_price"] == 51500.0
        assert closed_trades[0]["last_unrealized_pnl"] == 1875.0
        assert closed_trades[0]["close_reason"] == "flat"

    @pytest.mark.asyncio
    async def test_trader_current_state_writes_closed_trade_on_flip_and_starts_new_trade(
        self, repository: MemoryRepository
    ) -> None:
        """Short to long should close the short trade and open a new long trade."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0103"
        opened_at = datetime(2024, 1, 1, 12, 0, 0)
        flipped_at = opened_at + timedelta(minutes=5)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(-1.5, mark_price=49800, unrealized_pnl=300),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(0.75, entry_price=49750, mark_price=50100, unrealized_pnl=262.5),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=flipped_at,
            source="hyperliquid_ws",
        )

        state = await repository.get_trader_current_state(address)
        closed_trades = await repository.get_trader_closed_trades(
            address=address,
            start_time=opened_at - timedelta(hours=1),
        )

        assert state is not None
        assert state["btc_trade_meta"]["direction"] == "long"
        assert state["btc_trade_meta"]["opened_at"] == flipped_at
        assert state["btc_trade_meta"]["max_abs_size"] == 0.75
        assert len(closed_trades) == 1
        assert closed_trades[0]["dir"] == "short"
        assert closed_trades[0]["close_reason"] == "flip"

    @pytest.mark.asyncio
    async def test_trader_current_state_duplicate_close_event_is_idempotent(
        self, repository: MemoryRepository
    ) -> None:
        """Duplicate flat snapshots should not create duplicate closed trades."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0104"
        opened_at = datetime(2024, 1, 1, 12, 0, 0)
        closed_at = opened_at + timedelta(minutes=5)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=self.create_live_position(1.0, mark_price=50500, unrealized_pnl=500),
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=opened_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=closed_at,
            source="hyperliquid_ws",
        )
        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[],
            open_orders=[],
            margin_summary={"accountValue": 1000},
            event_timestamp=closed_at + timedelta(minutes=1),
            source="hyperliquid_ws",
        )

        closed_trades = await repository.get_trader_closed_trades(
            address=address,
            start_time=opened_at - timedelta(hours=1),
        )

        assert len(closed_trades) == 1

    @pytest.mark.asyncio
    async def test_derive_closed_trades_from_position_history_round_trip(
        self, repository: MemoryRepository
    ) -> None:
        """Backfill should derive one round-trip close from same-direction snapshots plus flat current state."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0105"
        opened_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        history = [
            {
                "eth": address.lower(),
                "t": opened_at,
                "coin": "BTC",
                "sz": 1.0,
                "ep": 50000,
                "mp": 50500,
                "upnl": 500,
                "lev": 2,
            },
            {
                "eth": address.lower(),
                "t": opened_at + timedelta(minutes=5),
                "coin": "BTC",
                "sz": 2.0,
                "ep": 50000,
                "mp": 51500,
                "upnl": 3000,
                "lev": 2,
            },
            {
                "eth": address.lower(),
                "t": opened_at + timedelta(minutes=10),
                "coin": "BTC",
                "sz": 1.0,
                "ep": 50000,
                "mp": 51200,
                "upnl": 1200,
                "lev": 2,
            },
        ]
        current_state = {
            "positions": [],
            "last_event_time": opened_at + timedelta(minutes=15),
        }

        trades = repository.derive_closed_trades_from_position_history(
            address=address,
            symbol="BTC",
            positions=history,
            current_state=current_state,
        )

        assert len(trades) == 1
        assert trades[0]["opened_at"] == opened_at
        assert trades[0]["closed_at"] == opened_at + timedelta(minutes=15)
        assert trades[0]["max_abs_size"] == 2.0
        assert trades[0]["final_abs_size"] == 1.0
        assert trades[0]["close_reason"] == "flat"

    @pytest.mark.asyncio
    async def test_derive_closed_trades_from_position_history_handles_flip(
        self, repository: MemoryRepository
    ) -> None:
        """Backfill should emit a close on direction flips and keep the new side open."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0106"
        opened_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        history = [
            {
                "eth": address.lower(),
                "t": opened_at,
                "coin": "BTC",
                "sz": -1.0,
                "ep": 50000,
                "mp": 49800,
                "upnl": 200,
                "lev": 2,
            },
            {
                "eth": address.lower(),
                "t": opened_at + timedelta(minutes=5),
                "coin": "BTC",
                "sz": -1.5,
                "ep": 50000,
                "mp": 49500,
                "upnl": 750,
                "lev": 2,
            },
            {
                "eth": address.lower(),
                "t": opened_at + timedelta(minutes=10),
                "coin": "BTC",
                "sz": 0.75,
                "ep": 49750,
                "mp": 50100,
                "upnl": 262.5,
                "lev": 2,
            },
        ]

        trades = repository.derive_closed_trades_from_position_history(
            address=address,
            symbol="BTC",
            positions=history,
            current_state={
                "positions": self.create_live_position(0.75, entry_price=49750, mark_price=50100),
                "last_event_time": opened_at + timedelta(minutes=10),
            },
        )

        assert len(trades) == 1
        assert trades[0]["dir"] == "short"
        assert trades[0]["close_reason"] == "flip"
        assert trades[0]["closed_at"] == opened_at + timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_store_trader_position_skips_duplicate_snapshot(
        self, repository: MemoryRepository
    ) -> None:
        """Position history does not keep identical consecutive snapshots."""
        position = {
            "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003",
            "t": datetime(2024, 1, 1, 12, 0, 0),
            "coin": "BTC",
            "sz": 1.25,
            "ep": 50000,
            "mp": 51000,
            "upnl": 1250,
            "lev": 2,
        }

        await repository.store_trader_position(position)
        await repository.store_trader_position({**position, "t": datetime(2024, 1, 1, 12, 5, 0)})

        assert len(repository._trader_positions_history) == 1

    @pytest.mark.asyncio
    async def test_store_trader_position_keeps_material_change(
        self, repository: MemoryRepository
    ) -> None:
        """Position history keeps snapshots when position values change."""
        base = {
            "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003",
            "t": datetime(2024, 1, 1, 12, 0, 0),
            "coin": "BTC",
            "sz": 1.25,
            "ep": 50000,
            "mp": 51000,
            "upnl": 1250,
            "lev": 2,
        }

        await repository.store_trader_position(base)
        await repository.store_trader_position(
            {**base, "t": datetime(2024, 1, 1, 12, 5, 0), "mp": 51500, "upnl": 1875}
        )

        assert len(repository._trader_positions_history) == 2

    @pytest.mark.asyncio
    async def test_store_trader_score_history(self, repository: MemoryRepository) -> None:
        """Score history can be stored via the repository abstraction."""
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.store_trader_score(
            {
                "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003",
                "t": event_time,
                "score": 88,
                "tags": ["whale"],
                "acct_val": 150000,
                "all_roi": 1.2,
                "month_roi": 0.2,
                "week_roi": 0.05,
            }
        )

        assert len(repository._trader_scores_history) == 1
        assert repository._trader_scores_history[0]["eth"] == (
            "0xabcdefabcdefabcdefabcdefabcdefabcdef0003"
        )

    @pytest.mark.asyncio
    async def test_store_trader_score_skips_duplicate_snapshot(
        self, repository: MemoryRepository
    ) -> None:
        """Score history does not keep identical consecutive snapshots."""
        score = {
            "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003",
            "t": datetime(2024, 1, 1, 12, 0, 0),
            "score": 88,
            "tags": ["whale", "elite"],
            "acct_val": 150000,
            "all_roi": 1.2,
            "month_roi": 0.2,
            "week_roi": 0.05,
        }

        await repository.store_trader_score(score)
        await repository.store_trader_score(
            {**score, "t": datetime(2024, 1, 1, 12, 5, 0), "tags": ["elite", "whale"]}
        )

        assert len(repository._trader_scores_history) == 1

    @pytest.mark.asyncio
    async def test_store_trader_score_keeps_material_change(
        self, repository: MemoryRepository
    ) -> None:
        """Score history keeps snapshots when score values change."""
        score = {
            "eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003",
            "t": datetime(2024, 1, 1, 12, 0, 0),
            "score": 88,
            "tags": ["whale"],
            "acct_val": 150000,
            "all_roi": 1.2,
            "month_roi": 0.2,
            "week_roi": 0.05,
        }

        await repository.store_trader_score(score)
        await repository.store_trader_score(
            {**score, "t": datetime(2024, 1, 1, 12, 5, 0), "score": 89}
        )

        assert len(repository._trader_scores_history) == 2

    @pytest.mark.asyncio
    async def test_store_and_get_canonical_candles(self, repository: MemoryRepository) -> None:
        """Canonical candle storage backs latest and historical candle queries."""
        first = Candle(
            t=datetime(2024, 1, 1, 12, 0, 0),
            o=50000,
            h=50500,
            l=49900,
            c=50400,
            v=12.5,
        )
        second = Candle(
            t=datetime(2024, 1, 1, 13, 0, 0),
            o=50400,
            h=51000,
            l=50350,
            c=50900,
            v=18.0,
        )

        await repository.store_candle(first, symbol="BTC", interval="1h")
        await repository.store_candle(second, symbol="BTC", interval="1h")

        latest = await repository.get_latest_candle("BTC", "1h")
        history = await repository.get_candles("BTC", "1h", limit=10)

        assert latest is not None
        assert latest["c"] == 50900
        assert len(history) == 2
        assert history[0]["t"] == first.t
        assert history[1]["t"] == second.t

    @pytest.mark.asyncio
    async def test_store_and_get_current_signal(self, repository: MemoryRepository) -> None:
        """Canonical signal storage backs current signal and stats queries."""
        first = TradingSignal(
            t=datetime(2024, 1, 1, 12, 0, 0),
            symbol="BTC",
            rec="BUY",
            conf=0.7,
            long_bias=0.7,
            short_bias=0.3,
            net_exp=1.1,
            t_long=10,
            t_short=3,
            t_flat=2,
            price=50000,
        )
        second = TradingSignal(
            t=datetime(2024, 1, 1, 13, 0, 0),
            symbol="BTC",
            rec="SELL",
            conf=0.8,
            long_bias=0.2,
            short_bias=0.8,
            net_exp=-1.4,
            t_long=2,
            t_short=11,
            t_flat=1,
            price=49000,
        )

        await repository.store_signal(first)
        await repository.store_signal(second)

        latest = await repository.get_current_signal("BTC")
        stats = await repository.get_signal_stats("BTC", start_time=datetime(2024, 1, 1, 0, 0, 0))

        assert latest is not None
        assert latest["rec"] == "SELL"
        assert stats["total"] == 2
        assert stats["buy"] == 1
        assert stats["sell"] == 1
