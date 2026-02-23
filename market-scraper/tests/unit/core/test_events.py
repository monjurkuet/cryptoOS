# tests/unit/core/test_events.py

"""Test suite for StandardEvent model."""

from datetime import UTC, datetime

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent


class TestStandardEvent:
    """Test suite for StandardEvent model."""

    def test_create_event(self) -> None:
        """Test event creation with factory method."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=datetime.now(UTC),
        )

        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload=payload.model_dump(),
        )

        assert event.event_id is not None
        assert event.event_type == EventType.TRADE
        assert event.source == "test"
        assert event.timestamp is not None
        assert event.correlation_id is not None

    def test_mark_processed(self) -> None:
        """Test marking event as processed."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.now(UTC).isoformat()},
        )

        assert event.processed_at is None
        assert event.processing_time_ms is None

        event.mark_processed()

        assert event.processed_at is not None
        assert event.processing_time_ms is not None
        assert event.processing_time_ms >= 0

    def test_event_serialization(self) -> None:
        """Test event JSON serialization."""
        event = StandardEvent.create(
            event_type=EventType.TICKER,
            source="hyperliquid",
            payload={
                "symbol": "ETH-USD",
                "price": 3000.0,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        json_str = event.model_dump_json()
        assert isinstance(json_str, str)
        assert "event_id" in json_str
        assert "BTC-USD" not in json_str  # Verify we didn't leak wrong data
        assert "ETH-USD" in json_str

    def test_invalid_priority(self) -> None:
        """Test priority validation."""
        with pytest.raises(ValueError):
            StandardEvent.create(
                event_type=EventType.TRADE,
                source="test",
                payload={
                    "symbol": "BTC-USD",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                priority=15,  # Invalid: > 10
            )

    def test_event_deserialization(self) -> None:
        """Test event JSON deserialization."""
        original_event = StandardEvent.create(
            event_type=EventType.OHLCV,
            source="test",
            payload={
                "symbol": "BTC-USD",
                "open": 50000.0,
                "high": 51000.0,
                "low": 49000.0,
                "close": 50500.0,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        json_str = original_event.model_dump_json()
        deserialized_event = StandardEvent.model_validate_json(json_str)

        assert deserialized_event.event_id == original_event.event_id
        assert deserialized_event.event_type == original_event.event_type
        assert deserialized_event.source == original_event.source

    def test_correlation_id_generation(self) -> None:
        """Test that correlation_id is auto-generated if not provided."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.now(UTC).isoformat()},
        )

        assert event.correlation_id is not None
        assert len(event.correlation_id) > 0

    def test_custom_correlation_id(self) -> None:
        """Test that custom correlation_id is used when provided."""
        custom_id = "custom-correlation-id-123"
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.now(UTC).isoformat()},
            correlation_id=custom_id,
        )

        assert event.correlation_id == custom_id


class TestMarketDataPayload:
    """Test suite for MarketDataPayload model."""

    def test_payload_creation(self) -> None:
        """Test creating a MarketDataPayload."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.5,
            timestamp=datetime.now(UTC),
            bid=49999.0,
            ask=50001.0,
        )

        assert payload.symbol == "BTC-USD"
        assert payload.price == 50000.0
        assert payload.volume == 1.5
        assert payload.bid == 49999.0
        assert payload.ask == 50001.0

    def test_payload_optional_fields(self) -> None:
        """Test that optional fields can be None."""
        payload = MarketDataPayload(
            symbol="ETH-USD",
            timestamp=datetime.now(UTC),
        )

        assert payload.price is None
        assert payload.volume is None
        assert payload.bid is None
        assert payload.ask is None

    def test_payload_extra_fields(self) -> None:
        """Test that extra fields are allowed."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=datetime.now(UTC),
            custom_field="custom_value",
        )

        assert payload.model_dump()["custom_field"] == "custom_value"
