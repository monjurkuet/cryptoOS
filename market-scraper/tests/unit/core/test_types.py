# tests/unit/core/test_types.py

"""Test suite for type aliases and constants."""

import pytest

from market_scraper.core.types import (
    VALID_TIMEFRAMES,
    ConnectorName,
    CorrelationId,
    EventId,
    Symbol,
)


class TestSymbol:
    """Test suite for Symbol type."""

    def test_symbol_creation(self) -> None:
        """Test Symbol type alias."""
        symbol = Symbol("BTC-USD")
        assert isinstance(symbol, str)
        assert symbol == "BTC-USD"

    def test_symbol_operations(self) -> None:
        """Test Symbol operations."""
        symbol = Symbol("ETH-USD")
        assert symbol.upper() == "ETH-USD"
        assert len(symbol) > 0


class TestConnectorName:
    """Test suite for ConnectorName type."""

    def test_connector_name_creation(self) -> None:
        """Test ConnectorName type alias."""
        name = ConnectorName("hyperliquid")
        assert isinstance(name, str)
        assert name == "hyperliquid"


class TestEventId:
    """Test suite for EventId type."""

    def test_event_id_creation(self) -> None:
        """Test EventId type alias."""
        event_id = EventId("123e4567-e89b-12d3-a456-426614174000")
        assert isinstance(event_id, str)
        assert event_id == "123e4567-e89b-12d3-a456-426614174000"


class TestCorrelationId:
    """Test suite for CorrelationId type."""

    def test_correlation_id_creation(self) -> None:
        """Test CorrelationId type alias."""
        correlation_id = CorrelationId("corr-123-456")
        assert isinstance(correlation_id, str)
        assert correlation_id == "corr-123-456"


class TestValidTimeframes:
    """Test suite for VALID_TIMEFRAMES constant."""

    def test_timeframes_list(self) -> None:
        """Test VALID_TIMEFRAMES contains expected values."""
        expected = ["1s", "1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        assert expected == VALID_TIMEFRAMES

    def test_timeframes_length(self) -> None:
        """Test VALID_TIMEFRAMES has correct length."""
        assert len(VALID_TIMEFRAMES) == 9

    @pytest.mark.parametrize("tf", ["1s", "1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"])
    def test_valid_timeframe_membership(self, tf: str) -> None:
        """Test each valid timeframe is in the list."""
        assert tf in VALID_TIMEFRAMES

    def test_invalid_timeframe_not_in_list(self) -> None:
        """Test invalid timeframe is not in the list."""
        assert "2h" not in VALID_TIMEFRAMES
        assert "30m" not in VALID_TIMEFRAMES
