"""
Helper Utilities.

This module provides common utility functions for the application.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, TypeVar

T = TypeVar("T")


def utcnow() -> datetime:
    """
    Get current UTC time.

    Returns:
        Current datetime in UTC with timezone info
    """
    return datetime.now(timezone.utc)


def timestamp_to_datetime(ts: int) -> datetime:
    """
    Convert Unix timestamp (milliseconds) to datetime.

    Args:
        ts: Unix timestamp in milliseconds

    Returns:
        Datetime object in UTC
    """
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime to Unix timestamp (milliseconds).

    Args:
        dt: Datetime object

    Returns:
        Unix timestamp in milliseconds
    """
    return int(dt.timestamp() * 1000)


def parse_float(value: Any) -> float:
    """
    Parse a value to float, handling various input types.

    Args:
        value: Value to parse (string, number, etc.)

    Returns:
        Parsed float value
    """
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def chunk_list(lst: List[T], size: int) -> List[List[T]]:
    """
    Split a list into chunks of specified size.

    Args:
        lst: List to split
        size: Maximum chunk size

    Returns:
        List of chunks
    """
    return [lst[i : i + size] for i in range(0, len(lst), size)]


async def gather_with_concurrency(
    tasks: List[Callable],
    limit: int = 10,
) -> List[Any]:
    """
    Execute async tasks with a concurrency limit.

    Args:
        tasks: List of async functions to execute
        limit: Maximum concurrent tasks

    Returns:
        List of results
    """
    semaphore = asyncio.Semaphore(limit)

    async def limited_task(task: Callable) -> Any:
        async with semaphore:
            return await task()

    return await asyncio.gather(*[limited_task(task) for task in tasks])


def format_address(address: str) -> str:
    """
    Format an Ethereum address for consistency.

    Args:
        address: Ethereum address

    Returns:
        Formatted address (lowercase, with 0x prefix)
    """
    if not address:
        return ""
    address = address.lower()
    if not address.startswith("0x"):
        address = f"0x{address}"
    return address


def truncate_address(address: str, start: int = 6, end: int = 4) -> str:
    """
    Truncate an Ethereum address for display.

    Args:
        address: Ethereum address
        start: Number of characters at start
        end: Number of characters at end

    Returns:
        Truncated address (e.g., "0x1234...5678")
    """
    if len(address) <= start + end:
        return address
    return f"{address[:start]}...{address[-end:]}"


def calculate_percentage_change(current: float, previous: float) -> float:
    """
    Calculate percentage change between two values.

    Args:
        current: Current value
        previous: Previous value

    Returns:
        Percentage change (-100 to +inf)
    """
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def format_large_number(value: float) -> str:
    """
    Format a large number with appropriate suffixes.

    Args:
        value: Number to format

    Returns:
        Formatted string (e.g., "1.5M", "2.3B")
    """
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    elif value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.2f}"


def calculate_time_ago(dt: datetime) -> str:
    """
    Calculate human-readable time ago string.

    Args:
        dt: Datetime to calculate from

    Returns:
        Human-readable string (e.g., "5 minutes ago")
    """
    now = utcnow()
    diff = now - dt

    seconds = int(diff.total_seconds())
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24

    if days > 0:
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif hours > 0:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif minutes > 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"
