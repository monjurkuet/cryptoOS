# tests/unit/processors/test_candle_processor.py

"""Test suite for CandleProcessor."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.candle_processor import CandleProcessor


class TestCandleProcessor:
    """Test suite for CandleProcessor."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock(return_value=True)
        return bus

    @pytest.fixture
    def processor(self, mock_event_bus: MagicMock) -> CandleProcessor:
        """Create a CandleProcessor instance with default timeframes."""
        return CandleProcessor(mock_event_bus, timeframes=[1, 5])

    @pytest.fixture
    def sample_trade(self) -> dict:
        """Create a sample trade."""
        return {
            "timestamp": datetime.utcnow(),
            "price": 50000.0,
            "volume": 1.0,
        }

    def test_init(self, mock_event_bus: MagicMock) -> None:
        """Test processor initialization."""
        processor = CandleProcessor(mock_event_bus, timeframes=[1, 5, 15])

        assert processor._event_bus == mock_event_bus
        assert processor._timeframes == [1, 5, 15]
        assert len(processor._candles) == 0
        assert len(processor._trades) == 0

    def test_init_default_timeframes(self, mock_event_bus: MagicMock) -> None:
        """Test default timeframes."""
        processor = CandleProcessor(mock_event_bus)

        assert processor._timeframes == [1, 5, 15]

    @pytest.mark.asyncio
    async def test_process_skips_non_trade_events(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test that non-trade events are passed through."""
        event = StandardEvent.create(
            event_type=EventType.TICKER,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
        )

        result = await processor.process(event)

        assert result == event

    @pytest.mark.asyncio
    async def test_process_accumulates_trades(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test that trade events are accumulated."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)

        assert "BTC-USD" in processor._trades
        assert len(processor._trades["BTC-USD"]) == 1
        assert processor._trades["BTC-USD"][0]["price"] == 50000.0

    @pytest.mark.asyncio
    async def test_process_updates_candles(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test that candles are updated with trades."""
        now = datetime.utcnow().replace(second=0, microsecond=0)
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=now,
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)

        candles = processor.get_candles("BTC-USD", 1)
        assert len(candles) == 1
        assert candles[0]["open"] == 50000.0
        assert candles[0]["high"] == 50000.0
        assert candles[0]["low"] == 50000.0
        assert candles[0]["close"] == 50000.0
        assert candles[0]["volume"] == 1.0

    @pytest.mark.asyncio
    async def test_process_updates_multiple_trades(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test candle updates with multiple trades."""
        now = datetime.utcnow().replace(second=0, microsecond=0)
        symbol = "BTC-USD"

        # Add multiple trades
        trades = [
            {"price": 50000.0, "volume": 1.0},
            {"price": 50100.0, "volume": 2.0},
            {"price": 49900.0, "volume": 1.5},
            {"price": 50050.0, "volume": 0.5},
        ]

        for i, trade in enumerate(trades):
            payload = MarketDataPayload(
                symbol=symbol,
                price=trade["price"],
                volume=trade["volume"],
                timestamp=now,
            )
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source="hyperliquid",
                payload=payload.model_dump(),
            )
            await processor.process(event)

        candles = processor.get_candles(symbol, 1)
        assert len(candles) == 1
        candle = candles[0]
        assert candle["open"] == 50000.0
        assert candle["high"] == 50100.0
        assert candle["low"] == 49900.0
        assert candle["close"] == 50050.0
        assert candle["volume"] == 5.0  # Sum of all volumes

    @pytest.mark.asyncio
    async def test_process_multiple_timeframes(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test candle creation for multiple timeframes."""
        now = datetime.utcnow().replace(second=0, microsecond=0)
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=now,
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)

        # Should have candles for both 1-min and 5-min timeframes
        candles_1m = processor.get_candles("BTC-USD", 1)
        candles_5m = processor.get_candles("BTC-USD", 5)

        assert len(candles_1m) == 1
        assert len(candles_5m) == 1

    @pytest.mark.asyncio
    async def test_process_invalid_event(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test handling of invalid events."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "", "timestamp": datetime.utcnow().isoformat()},
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_missing_price(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test handling of events with missing price."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={
                "symbol": "BTC-USD",
                "timestamp": datetime.utcnow().isoformat(),
                "volume": 1.0,
            },
        )

        result = await processor.process(event)

        assert result is None

    def test_aggregate_candles(self, processor: CandleProcessor) -> None:
        """Test the _aggregate_candles method."""
        now = datetime.utcnow().replace(second=0, microsecond=0)
        trades = [
            {"timestamp": now, "price": 50000.0, "volume": 1.0},
            {"timestamp": now + timedelta(seconds=30), "price": 50100.0, "volume": 2.0},
        ]

        candles = processor._aggregate_candles(trades, 1)

        assert len(candles) == 1
        assert candles[0]["open"] == 50000.0
        assert candles[0]["high"] == 50100.0
        assert candles[0]["low"] == 50000.0
        assert candles[0]["close"] == 50100.0
        assert candles[0]["volume"] == 3.0

    def test_aggregate_candles_empty(self, processor: CandleProcessor) -> None:
        """Test aggregation with empty trades."""
        candles = processor._aggregate_candles([], 1)
        assert candles == []

    @pytest.mark.asyncio
    async def test_flush_completes_candles(
        self,
        processor: CandleProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that flush emits completed candles."""
        # Create a trade in the past (more than 5 minutes ago to ensure both timeframes complete)
        past_time = datetime.utcnow() - timedelta(minutes=6)
        past_time = past_time.replace(second=0, microsecond=0)

        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=past_time,
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)

        # Flush should emit the completed candle
        completed = await processor.flush()

        assert len(completed) == 2  # 1 for each timeframe
        mock_event_bus.publish.assert_called()

        # Candles should be cleared after flush
        candles = processor.get_candles("BTC-USD", 1)
        assert len(candles) == 0

    @pytest.mark.asyncio
    async def test_flush_no_completed_candles(
        self,
        processor: CandleProcessor,
    ) -> None:
        """Test flush with no completed candles."""
        # Create a trade in the current minute
        now = datetime.utcnow().replace(second=0, microsecond=0)

        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=now,
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)

        # Flush should not emit incomplete candles
        completed = await processor.flush()

        assert len(completed) == 0

    def test_get_candles_no_data(self, processor: CandleProcessor) -> None:
        """Test get_candles with no data."""
        candles = processor.get_candles("BTC-USD", 1)
        assert candles == []

    @pytest.mark.asyncio
    async def test_stop_flushes_candles(
        self,
        processor: CandleProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that stop flushes remaining candles."""
        past_time = datetime.utcnow() - timedelta(minutes=2)
        past_time = past_time.replace(second=0, microsecond=0)

        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.0,
            timestamp=past_time,
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        await processor.process(event)
        await processor.stop()

        assert processor.is_running is False
