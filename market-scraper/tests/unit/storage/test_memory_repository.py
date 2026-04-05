"""Tests for the MemoryRepository implementation."""

from datetime import UTC, datetime, timedelta

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.storage.base import QueryFilter
from market_scraper.storage.memory_repository import MemoryRepository


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
    async def test_trader_current_state_and_history(self, repository: MemoryRepository):
        """Current state and position history are persisted for traders."""
        address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0003"
        event_time = datetime(2024, 1, 1, 12, 0, 0)

        await repository.upsert_trader_current_state(
            address=address,
            symbol="BTC",
            positions=[{"position": {"coin": "BTC", "szi": 1.25}}],
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
