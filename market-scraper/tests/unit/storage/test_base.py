"""Tests for the storage base module."""

from datetime import datetime

import pytest

from market_scraper.storage.base import QueryFilter


class TestQueryFilter:
    """Test suite for QueryFilter model."""

    def test_default_values(self):
        """Test QueryFilter with default values."""
        filter_ = QueryFilter()

        assert filter_.symbol is None
        assert filter_.event_type is None
        assert filter_.start_time is None
        assert filter_.end_time is None
        assert filter_.source is None
        assert filter_.limit == 1000
        assert filter_.offset == 0

    def test_custom_values(self):
        """Test QueryFilter with custom values."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        end = datetime(2024, 1, 31, 23, 59, 59)

        filter_ = QueryFilter(
            symbol="BTC-USD",
            event_type="trade",
            start_time=start,
            end_time=end,
            source="hyperliquid",
            limit=100,
            offset=50,
        )

        assert filter_.symbol == "BTC-USD"
        assert filter_.event_type == "trade"
        assert filter_.start_time == start
        assert filter_.end_time == end
        assert filter_.source == "hyperliquid"
        assert filter_.limit == 100
        assert filter_.offset == 50

    def test_limit_validation(self):
        """Test limit field validation."""
        # Valid limit
        filter_ = QueryFilter(limit=500)
        assert filter_.limit == 500

        # Limit at boundary
        filter_ = QueryFilter(limit=1)
        assert filter_.limit == 1

        filter_ = QueryFilter(limit=10000)
        assert filter_.limit == 10000

        # Invalid limits
        with pytest.raises(ValueError):
            QueryFilter(limit=0)

        with pytest.raises(ValueError):
            QueryFilter(limit=-1)

        with pytest.raises(ValueError):
            QueryFilter(limit=10001)

    def test_offset_validation(self):
        """Test offset field validation."""
        # Valid offsets
        filter_ = QueryFilter(offset=0)
        assert filter_.offset == 0

        filter_ = QueryFilter(offset=100)
        assert filter_.offset == 100

        # Invalid offsets
        with pytest.raises(ValueError):
            QueryFilter(offset=-1)

    def test_model_serialization(self):
        """Test QueryFilter serialization."""
        start = datetime(2024, 1, 1, 0, 0, 0)
        filter_ = QueryFilter(
            symbol="ETH-USD",
            event_type="ticker",
            start_time=start,
            limit=500,
            offset=10,
        )

        json_str = filter_.model_dump_json()
        assert "ETH-USD" in json_str
        assert "ticker" in json_str

        # Deserialize
        loaded = QueryFilter.model_validate_json(json_str)
        assert loaded.symbol == "ETH-USD"
        assert loaded.event_type == "ticker"
        assert loaded.limit == 500
        assert loaded.offset == 10
