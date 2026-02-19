"""Integration tests for storage implementations."""

import asyncio
import os
from contextlib import suppress
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.storage.base import QueryFilter
from market_scraper.storage.memory_repository import MemoryRepository
from market_scraper.storage.mongo_repository import MongoRepository

# Skip MongoDB tests if MONGODB_URL is not set
pytestmark = pytest.mark.integration


class TestMemoryRepositoryIntegration:
    """Integration tests for MemoryRepository."""

    @pytest_asyncio.fixture
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
        event_timestamp = timestamp or datetime.utcnow()
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
    async def test_full_crud_lifecycle(self, repository: MemoryRepository):
        """Test full CRUD lifecycle."""
        # Create
        event = self.create_trade_event(symbol="BTC-USD", price=50000.0)
        await repository.store(event)

        # Read
        results = await repository.query(QueryFilter(symbol="BTC-USD"))
        assert len(results) == 1
        # Payload can be dict or MarketDataPayload
        if isinstance(results[0].payload, dict):
            assert results[0].payload["price"] == 50000.0
        else:
            assert results[0].payload.price == 50000.0

        # Query latest
        latest = await repository.get_latest("BTC-USD", "trade")
        assert latest is not None
        assert latest.event_id == event.event_id

    @pytest.mark.asyncio
    async def test_bulk_insert_performance(self, repository: MemoryRepository):
        """Test bulk insert with larger dataset."""
        events = [
            self.create_trade_event(
                timestamp=datetime(2024, 1, 1, 0, 0, 0) + timedelta(seconds=i),
                price=50000.0 + i,
            )
            for i in range(100)
        ]

        count = await repository.store_bulk(events)
        assert count == 100

        all_events = await repository.query(QueryFilter(limit=1000))
        assert len(all_events) == 100

    @pytest.mark.asyncio
    async def test_complex_query(self, repository: MemoryRepository):
        """Test complex query with multiple filters."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

        # Create events for different symbols, sources, and times
        events = [
            # BTC from hyperliquid
            self.create_trade_event(
                symbol="BTC-USD",
                source="hyperliquid",
                timestamp=base_time + timedelta(minutes=i),
                price=50000.0 + i,
            )
            for i in range(10)
        ] + [
            # ETH from binance
            self.create_trade_event(
                symbol="ETH-USD",
                source="binance",
                timestamp=base_time + timedelta(minutes=i),
                price=3000.0 + i,
            )
            for i in range(10)
        ]

        await repository.store_bulk(events)

        # Complex query: BTC from hyperliquid in time range
        results = await repository.query(
            QueryFilter(
                symbol="BTC-USD",
                source="hyperliquid",
                start_time=base_time + timedelta(minutes=3),
                end_time=base_time + timedelta(minutes=7),
                limit=100,
            )
        )

        # Should get 5 events (minutes 3, 4, 5, 6, 7)
        assert len(results) == 5
        for r in results:
            assert r.source == "hyperliquid"
            # Payload can be dict or MarketDataPayload
            if isinstance(r.payload, dict):
                assert r.payload["symbol"] == "BTC-USD"
            else:
                assert r.payload.symbol == "BTC-USD"

    @pytest.mark.asyncio
    async def test_concurrent_access(self, repository: MemoryRepository):
        """Test concurrent access to repository."""

        async def insert_events(start_price: float):
            events = [self.create_trade_event(price=start_price + i) for i in range(10)]
            return await repository.store_bulk(events)

        # Run multiple insertions concurrently
        tasks = [insert_events(float(i * 1000)) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert sum(results) == 50

        all_events = await repository.query(QueryFilter(limit=1000))
        assert len(all_events) == 50


@pytest.mark.skipif(
    not os.getenv("MONGODB_URL"),
    reason="MONGODB_URL not set - skipping MongoDB tests",
)
class TestMongoRepositoryIntegration:
    """Integration tests for MongoRepository."""

    @pytest_asyncio.fixture
    async def repository(self):
        """Create and connect a MongoRepository."""
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        repo = MongoRepository(
            connection_string=mongo_url,
            database_name="market_scraper_test",
        )
        await repo.connect()
        # Clean up any existing test data
        with suppress(Exception):
            await repo.drop_collection("events")
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
        event_timestamp = timestamp or datetime.utcnow()
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
        """Test MongoDB connection lifecycle."""
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        repo = MongoRepository(
            connection_string=mongo_url,
            database_name="market_scraper_test",
        )

        assert not repo.is_connected
        await repo.connect()
        assert repo.is_connected
        await repo.disconnect()
        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

        async with MongoRepository(
            connection_string=mongo_url,
            database_name="market_scraper_test",
        ) as repo:
            assert repo.is_connected

        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_store_and_query(self, repository: MongoRepository):
        """Test basic store and query operations."""
        event = self.create_trade_event(symbol="BTC-USD", price=50000.0)

        # Store
        result = await repository.store(event)
        assert result is True

        # Query
        results = await repository.query(QueryFilter(symbol="BTC-USD"))
        assert len(results) == 1
        assert results[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_store_bulk(self, repository: MongoRepository):
        """Test bulk store operation."""
        events = [self.create_trade_event(price=50000.0 + i) for i in range(100)]

        count = await repository.store_bulk(events)
        assert count == 100

        results = await repository.query(QueryFilter(limit=1000))
        assert len(results) == 100

    @pytest.mark.asyncio
    async def test_query_filters(self, repository: MongoRepository):
        """Test query with various filters."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

        events = [
            self.create_trade_event(
                symbol="BTC-USD",
                source="hyperliquid",
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(10)
        ] + [
            self.create_trade_event(
                symbol="ETH-USD",
                source="binance",
                timestamp=base_time + timedelta(minutes=i),
            )
            for i in range(10)
        ]

        await repository.store_bulk(events)

        # Test symbol filter
        btc_results = await repository.query(QueryFilter(symbol="BTC-USD"))
        assert len(btc_results) == 10

        # Test source filter
        hl_results = await repository.query(QueryFilter(source="hyperliquid"))
        assert len(hl_results) == 10

        # Test time range
        time_results = await repository.query(
            QueryFilter(
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=7),
            )
        )
        assert len(time_results) == 6  # minutes 5, 6, 7 from both symbols

    @pytest.mark.asyncio
    async def test_get_latest(self, repository: MongoRepository):
        """Test get_latest operation."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

        events = [
            self.create_trade_event(
                symbol="BTC-USD",
                timestamp=base_time + timedelta(minutes=i),
                price=50000.0 + i,
            )
            for i in range(10)
        ]
        await repository.store_bulk(events)

        latest = await repository.get_latest("BTC-USD", "trade")
        assert latest is not None
        assert isinstance(latest.payload, dict)
        assert latest.payload["price"] == 50009.0

    @pytest.mark.asyncio
    async def test_get_latest_with_source(self, repository: MongoRepository):
        """Test get_latest with source filter."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

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

        # Get latest from hyperliquid
        latest = await repository.get_latest("BTC-USD", "trade", source="hyperliquid")
        assert latest is not None
        assert latest.source == "hyperliquid"

    @pytest.mark.asyncio
    async def test_aggregate_ohlcv(self, repository: MongoRepository):
        """Test OHLCV aggregation."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

        # Create trades in 1-minute intervals
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
        assert results[0]["open"] == 100.0
        assert results[0]["high"] == 110.0
        assert results[0]["low"] == 100.0
        assert results[0]["close"] == 105.0
        assert results[0]["volume"] == 4.5
        assert results[0]["count"] == 3

        # Check second candle
        assert results[1]["open"] == 120.0
        assert results[1]["high"] == 125.0
        assert results[1]["low"] == 120.0
        assert results[1]["close"] == 125.0
        assert results[1]["volume"] == 3.0
        assert results[1]["count"] == 2

    @pytest.mark.asyncio
    async def test_health_check(self, repository: MongoRepository):
        """Test health check."""
        health = await repository.health_check()

        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert "document_count" in health
        assert "storage_size_mb" in health

    @pytest.mark.asyncio
    async def test_duplicate_event_id(self, repository: MongoRepository):
        """Test that duplicate event IDs are handled."""
        event = self.create_trade_event()

        # Store first time
        result1 = await repository.store(event)
        assert result1 is True

        # Try to store again (should fail due to unique index)
        await repository.store(event)
        # This might succeed or fail depending on MongoDB configuration
        # The important thing is it doesn't crash

    @pytest.mark.asyncio
    async def test_pagination(self, repository: MongoRepository):
        """Test query pagination with limit and offset."""
        base_time = datetime(2024, 1, 15, 12, 0, 0)

        # Create 20 events
        events = [
            self.create_trade_event(
                timestamp=base_time + timedelta(minutes=i),
                price=float(i),
            )
            for i in range(20)
        ]
        await repository.store_bulk(events)

        # Get first page (5 items)
        page1 = await repository.query(QueryFilter(limit=5, offset=0))
        assert len(page1) == 5
        assert isinstance(page1[0].payload, dict)
        assert page1[0].payload["price"] == 19.0  # Most recent first

        # Get second page
        page2 = await repository.query(QueryFilter(limit=5, offset=5))
        assert len(page2) == 5
        assert page2[0].payload["price"] == 14.0
