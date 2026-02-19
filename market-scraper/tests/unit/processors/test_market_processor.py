# tests/unit/processors/test_market_processor.py

"""Test suite for MarketDataProcessor."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.market_processor import MarketDataProcessor


class TestMarketDataProcessor:
    """Test suite for MarketDataProcessor."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.publish = AsyncMock(return_value=True)
        return bus

    @pytest.fixture
    def processor(self, mock_event_bus: MagicMock) -> MarketDataProcessor:
        """Create a MarketDataProcessor instance."""
        return MarketDataProcessor(mock_event_bus)

    @pytest.fixture
    def sample_trade_event(self) -> StandardEvent:
        """Create a sample trade event."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.5,
            timestamp=datetime.utcnow(),
        )
        return StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

    @pytest.mark.asyncio
    async def test_init(self, mock_event_bus: MagicMock) -> None:
        """Test processor initialization."""
        processor = MarketDataProcessor(mock_event_bus)

        assert processor._event_bus == mock_event_bus
        assert "hyperliquid" in processor._symbol_normalizers
        assert "cbbi" in processor._symbol_normalizers

    @pytest.mark.asyncio
    async def test_process_skips_non_market_events(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that non-market events are passed through."""
        event = StandardEvent.create(
            event_type=EventType.ERROR,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
        )

        result = await processor.process(event)

        assert result == event
        mock_event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_normalizes_hyperliquid_symbol(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test Hyperliquid symbol normalization."""
        payload = MarketDataPayload(
            symbol="BTC@USD",
            price=50000.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is not None
        assert result.payload.symbol == "BTC-USD"

    @pytest.mark.asyncio
    async def test_process_normalizes_hyperliquid_bare_symbol(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test Hyperliquid bare symbol normalization."""
        payload = MarketDataPayload(
            symbol="eth",
            price=3000.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TICKER,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is not None
        assert result.payload.symbol == "ETH-USD"

    @pytest.mark.asyncio
    async def test_process_normalizes_cbbi_symbol(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test CBBI symbol normalization."""
        payload = MarketDataPayload(
            symbol="btc-usd",
            price=50000.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TICKER,
            source="cbbi",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is not None
        assert result.payload.symbol == "BTC-USD"

    @pytest.mark.asyncio
    async def test_process_uses_default_normalizer(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test default normalizer for unknown sources."""
        payload = MarketDataPayload(
            symbol="btc-usd",
            price=50000.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="unknown_source",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is not None
        assert result.payload.symbol == "BTC-USD"

    @pytest.mark.asyncio
    async def test_validate_payload_rejects_zero_price(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation rejects zero price."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=0.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_payload_rejects_negative_price(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation rejects negative price."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=-100.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_payload_rejects_excessive_price(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation rejects excessively high price."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=1e13,  # > 1e12
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_payload_rejects_negative_volume(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation rejects negative volume."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=-1.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_payload_rejects_invalid_ohlcv(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation rejects high < low."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            high=40000.0,
            low=50000.0,  # high < low
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.OHLCV,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_payload_accepts_valid_ohlcv(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test validation accepts valid OHLCV."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            high=51000.0,
            low=49000.0,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.OHLCV,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

        result = await processor.process(event)

        assert result is not None

    @pytest.mark.asyncio
    async def test_process_publishes_normalized_event(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
        sample_trade_event: StandardEvent,
    ) -> None:
        """Test that normalized events are published."""
        await processor.process(sample_trade_event)

        mock_event_bus.publish.assert_called_once()
        published_event = mock_event_bus.publish.call_args[0][0]
        assert isinstance(published_event, StandardEvent)
        assert published_event.parent_event_id == sample_trade_event.event_id

    @pytest.mark.asyncio
    async def test_process_handles_dict_payload(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test processing with dict payload."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload={
                "symbol": "ETH@USD",
                "price": 3000.0,
                "volume": 2.0,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        result = await processor.process(event)

        assert result is not None
        assert result.payload.symbol == "ETH-USD"

    @pytest.mark.asyncio
    async def test_process_handles_invalid_payload_type(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test processing with invalid payload type."""
        # Create an event with a dict payload that lacks required fields
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
        )
        # Set payload to an invalid type
        event.payload = "invalid_payload"  # type: ignore[assignment]

        result = await processor.process(event)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_handles_exception(
        self,
        processor: MarketDataProcessor,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test handling of exceptions during processing."""
        # Create a properly mocked event with all required attributes
        from datetime import datetime as dt

        event = MagicMock()
        event.event_type = EventType.TRADE
        event.source = "hyperliquid"
        event.payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=dt.utcnow(),
        )
        event.event_id = "test-id"
        event.correlation_id = "corr-id"
        event.priority = 5
        event.timestamp = dt.utcnow()
        event.parent_event_id = None

        result = await processor.process(event)

        assert result is not None

    def test_normalize_hyperliquid_symbol(self, processor: MarketDataProcessor) -> None:
        """Test _normalize_hyperliquid_symbol method."""
        assert processor._normalize_hyperliquid_symbol("BTC@USD") == "BTC-USD"
        assert processor._normalize_hyperliquid_symbol("eth") == "ETH-USD"
        assert processor._normalize_hyperliquid_symbol("SOL-USD") == "SOL-USD"
        assert processor._normalize_hyperliquid_symbol("xrp@usd") == "XRP-USD"

    def test_normalize_cbbi_symbol(self, processor: MarketDataProcessor) -> None:
        """Test _normalize_cbbi_symbol method."""
        assert processor._normalize_cbbi_symbol("btc-usd") == "BTC-USD"
        assert processor._normalize_cbbi_symbol("ETH") == "ETH"
        assert processor._normalize_cbbi_symbol("Sol-UsD") == "SOL-USD"

    def test_default_normalizer(self, processor: MarketDataProcessor) -> None:
        """Test _default_normalizer method."""
        assert processor._default_normalizer("btc-usd") == "BTC-USD"
        assert processor._default_normalizer("ETH") == "ETH"

    def test_validate_payload_empty_symbol(self, processor: MarketDataProcessor) -> None:
        """Test validation rejects empty symbol."""
        payload = MarketDataPayload(
            symbol="",
            timestamp=datetime.utcnow(),
        )
        assert processor._validate_payload(payload) is False

    def test_validate_payload_accepts_none_price(self, processor: MarketDataProcessor) -> None:
        """Test validation accepts None price."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=None,
            timestamp=datetime.utcnow(),
        )
        assert processor._validate_payload(payload) is True

    def test_validate_payload_accepts_none_volume(self, processor: MarketDataProcessor) -> None:
        """Test validation accepts None volume."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            volume=None,
            timestamp=datetime.utcnow(),
        )
        assert processor._validate_payload(payload) is True
