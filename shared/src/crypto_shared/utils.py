"""Safe type conversion utilities.

Provides functions for safely converting values with default fallbacks
to prevent crashes from malformed data.
"""

from datetime import datetime
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float with default on error."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int with default on error."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_datetime(
    value: str | None,
    default: datetime | None = None,
) -> datetime | None:
    """Safely parse an ISO datetime string with default on error."""
    if value is None:
        return default
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert a value to string with default on error."""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default
