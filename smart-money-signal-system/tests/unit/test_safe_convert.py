"""Tests for safe conversion utilities."""

import pytest
from datetime import datetime, timezone

from signal_system.utils.safe_convert import (
    safe_float,
    safe_int,
    safe_datetime,
    safe_str,
)


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_float_input(self) -> None:
        """Test with float input."""
        assert safe_float(123.45) == 123.45

    def test_int_input(self) -> None:
        """Test with int input."""
        assert safe_float(123) == 123.0

    def test_string_input(self) -> None:
        """Test with string input."""
        assert safe_float("123.45") == 123.45
        assert safe_float("123") == 123.0

    def test_none_input(self) -> None:
        """Test with None input returns default."""
        assert safe_float(None) == 0.0
        assert safe_float(None, default=5.0) == 5.0

    def test_invalid_string(self) -> None:
        """Test with invalid string returns default."""
        assert safe_float("invalid") == 0.0
        assert safe_float("invalid", default=99.0) == 99.0

    def test_empty_string(self) -> None:
        """Test with empty string returns default."""
        assert safe_float("") == 0.0

    def test_negative_value(self) -> None:
        """Test with negative value."""
        assert safe_float(-123.45) == -123.45
        assert safe_float("-123.45") == -123.45


class TestSafeInt:
    """Tests for safe_int function."""

    def test_int_input(self) -> None:
        """Test with int input."""
        assert safe_int(123) == 123

    def test_float_input(self) -> None:
        """Test with float input (truncates)."""
        assert safe_int(123.99) == 123

    def test_string_input(self) -> None:
        """Test with string input."""
        assert safe_int("123") == 123

    def test_none_input(self) -> None:
        """Test with None input returns default."""
        assert safe_int(None) == 0
        assert safe_int(None, default=42) == 42

    def test_invalid_string(self) -> None:
        """Test with invalid string returns default."""
        assert safe_int("invalid") == 0
        assert safe_int("invalid", default=99) == 99


class TestSafeDatetime:
    """Tests for safe_datetime function."""

    def test_iso_string(self) -> None:
        """Test with ISO format string."""
        result = safe_datetime("2024-01-15T12:30:00+00:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_iso_string_with_z(self) -> None:
        """Test with Z suffix (UTC)."""
        result = safe_datetime("2024-01-15T12:30:00Z")
        assert result is not None
        assert result.year == 2024

    def test_none_input(self) -> None:
        """Test with None input returns default."""
        assert safe_datetime(None) is None
        default = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert safe_datetime(None, default=default) == default

    def test_invalid_string(self) -> None:
        """Test with invalid string returns default."""
        assert safe_datetime("invalid") is None
        assert safe_datetime("not-a-date") is None

    def test_empty_string(self) -> None:
        """Test with empty string returns default."""
        assert safe_datetime("") is None


class TestSafeStr:
    """Tests for safe_str function."""

    def test_string_input(self) -> None:
        """Test with string input."""
        assert safe_str("hello") == "hello"

    def test_int_input(self) -> None:
        """Test with int input."""
        assert safe_str(123) == "123"

    def test_none_input(self) -> None:
        """Test with None input returns default."""
        assert safe_str(None) == ""
        assert safe_str(None, default="default") == "default"

    def test_list_input(self) -> None:
        """Test with list input."""
        assert safe_str([1, 2, 3]) == "[1, 2, 3]"
