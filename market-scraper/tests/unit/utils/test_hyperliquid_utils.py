# tests/unit/utils/test_hyperliquid.py

"""Tests for Hyperliquid utility functions."""


from market_scraper.utils.hyperliquid import (
    extract_pnl,
    extract_roi,
    extract_volume,
    is_positive_roi,
    parse_window_performances,
)


class TestParseWindowPerformances:
    """Tests for parse_window_performances function."""

    def test_empty_input(self) -> None:
        """Test with empty input."""
        assert parse_window_performances([]) == {}
        assert parse_window_performances({}) == {}
        assert parse_window_performances(None) == {}

    def test_list_format(self) -> None:
        """Test parsing list format (most common from Hyperliquid API)."""
        performances = [
            ["day", {"pnl": 1000, "roi": 0.05, "vlm": 50000}],
            ["week", {"pnl": 5000, "roi": 0.15, "vlm": 200000}],
            ["month", {"pnl": 15000, "roi": 0.35, "vlm": 800000}],
        ]

        result = parse_window_performances(performances)

        assert "day" in result
        assert "week" in result
        assert "month" in result
        assert result["day"]["pnl"] == 1000.0
        assert result["day"]["roi"] == 0.05
        assert result["day"]["vlm"] == 50000.0

    def test_dict_format(self) -> None:
        """Test parsing dict format."""
        performances = {
            "day": {"pnl": 1000, "roi": 0.05, "vlm": 50000},
            "week": {"pnl": 5000, "roi": 0.15, "vlm": 200000},
        }

        result = parse_window_performances(performances)

        assert result["day"]["pnl"] == 1000.0
        assert result["week"]["roi"] == 0.15

    def test_missing_fields(self) -> None:
        """Test handling of missing fields."""
        performances = [
            ["day", {"pnl": 1000}],  # Missing roi and vlm
        ]

        result = parse_window_performances(performances)

        assert result["day"]["pnl"] == 1000.0
        assert result["day"]["roi"] == 0.0
        assert result["day"]["vlm"] == 0.0

    def test_null_values(self) -> None:
        """Test handling of null values."""
        performances = [
            ["day", {"pnl": None, "roi": None, "vlm": None}],
        ]

        result = parse_window_performances(performances)

        assert result["day"]["pnl"] == 0.0
        assert result["day"]["roi"] == 0.0
        assert result["day"]["vlm"] == 0.0

    def test_all_time_window(self) -> None:
        """Test parsing allTime window."""
        performances = [
            ["allTime", {"pnl": 100000, "roi": 2.5, "vlm": 5000000}],
        ]

        result = parse_window_performances(performances)

        assert "allTime" in result
        assert result["allTime"]["roi"] == 2.5

    def test_short_list_skipped(self) -> None:
        """Test that lists with fewer than 2 elements are skipped."""
        performances = [
            ["day"],  # Missing metrics
            ["week", {"pnl": 1000, "roi": 0.05, "vlm": 50000}],
        ]

        result = parse_window_performances(performances)

        assert "day" not in result
        assert "week" in result


class TestExtractRoi:
    """Tests for extract_roi function."""

    def test_extract_existing_roi(self) -> None:
        """Test extracting ROI from existing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_roi(performances, "day") == 0.05

    def test_extract_missing_window(self) -> None:
        """Test extracting ROI from missing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_roi(performances, "week") == 0.0

    def test_extract_null_roi(self) -> None:
        """Test extracting null ROI."""
        performances = {"day": {"pnl": 1000, "roi": None, "vlm": 50000}}
        assert extract_roi(performances, "day") == 0.0


class TestExtractPnl:
    """Tests for extract_pnl function."""

    def test_extract_existing_pnl(self) -> None:
        """Test extracting PnL from existing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_pnl(performances, "day") == 1000.0

    def test_extract_missing_window(self) -> None:
        """Test extracting PnL from missing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_pnl(performances, "week") == 0.0


class TestExtractVolume:
    """Tests for extract_volume function."""

    def test_extract_existing_volume(self) -> None:
        """Test extracting volume from existing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_volume(performances, "day") == 50000.0

    def test_extract_missing_window(self) -> None:
        """Test extracting volume from missing window."""
        performances = {"day": {"pnl": 1000, "roi": 0.05, "vlm": 50000}}
        assert extract_volume(performances, "week") == 0.0


class TestIsPositiveRoi:
    """Tests for is_positive_roi function."""

    def test_all_positive(self) -> None:
        """Test when all ROIs are positive."""
        performances = {
            "day": {"pnl": 1000, "roi": 0.05, "vlm": 50000},
            "week": {"pnl": 5000, "roi": 0.15, "vlm": 200000},
            "month": {"pnl": 15000, "roi": 0.35, "vlm": 800000},
        }
        assert is_positive_roi(performances, "day", "week", "month") is True

    def test_one_negative(self) -> None:
        """Test when one ROI is negative."""
        performances = {
            "day": {"pnl": -500, "roi": -0.05, "vlm": 50000},
            "week": {"pnl": 5000, "roi": 0.15, "vlm": 200000},
            "month": {"pnl": 15000, "roi": 0.35, "vlm": 800000},
        }
        assert is_positive_roi(performances, "day", "week", "month") is False

    def test_one_zero(self) -> None:
        """Test when one ROI is zero."""
        performances = {
            "day": {"pnl": 0, "roi": 0.0, "vlm": 50000},
            "week": {"pnl": 5000, "roi": 0.15, "vlm": 200000},
        }
        assert is_positive_roi(performances, "day", "week") is False

    def test_missing_window(self) -> None:
        """Test when a window is missing."""
        performances = {
            "day": {"pnl": 1000, "roi": 0.05, "vlm": 50000},
        }
        assert is_positive_roi(performances, "day", "week") is False  # week missing

    def test_empty_performances(self) -> None:
        """Test with empty performances."""
        assert is_positive_roi({}, "day") is False
