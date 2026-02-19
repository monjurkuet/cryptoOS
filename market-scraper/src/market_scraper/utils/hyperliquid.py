# src/market_scraper/utils/hyperliquid.py

"""Hyperliquid-specific utility functions.

This module contains shared utility functions for parsing and processing
Hyperliquid data across the codebase.
"""

from typing import Any


def parse_window_performances(performances: Any) -> dict[str, dict]:
    """Parse Hyperliquid window performances into standard format.

    Converts raw performance data from Hyperliquid API into a dict
    keyed by time window ('day', 'week', 'month', 'year', 'allTime').

    Hyperliquid returns performances in two possible formats:
    1. List of [window_name, metrics_dict] pairs (most common)
    2. Dict already keyed by window name

    Args:
        performances: Raw performance data from Hyperliquid API.
            Can be a list of pairs or a dict.

    Returns:
        Dict mapping window name to performance metrics:
        - pnl: Profit and loss in USD
        - roi: Return on investment as decimal (e.g., 0.15 = 15%)
        - vlm: Trading volume in USD

    Examples:
        >>> performances = [["day", {"pnl": 1000, "roi": 0.05, "vlm": 50000}}]
        >>> parse_window_performances(performances)
        {'day': {'pnl': 1000.0, 'roi': 0.05, 'vlm': 50000.0}}

        >>> performances = {"day": {"pnl": 1000, "roi": 0.05}}
        >>> parse_window_performances(performances)
        {'day': {'pnl': 1000, 'roi': 0.05}}
    """
    if not performances:
        return {}

    # If already a dict, return as-is (but ensure values have correct types)
    if isinstance(performances, dict):
        result = {}
        for window, metrics in performances.items():
            if isinstance(metrics, dict):
                result[window] = {
                    "pnl": float(metrics.get("pnl", 0) or 0),
                    "roi": float(metrics.get("roi", 0) or 0),
                    "vlm": float(metrics.get("vlm", 0) or 0),
                }
            else:
                result[window] = metrics
        return result

    # If a list, convert to dict
    if isinstance(performances, list):
        result = {}
        for window_data in performances:
            if isinstance(window_data, list) and len(window_data) >= 2:
                window = window_data[0]
                metrics = window_data[1]
                if isinstance(metrics, dict):
                    result[window] = {
                        "pnl": float(metrics.get("pnl", 0) or 0),
                        "roi": float(metrics.get("roi", 0) or 0),
                        "vlm": float(metrics.get("vlm", 0) or 0),
                    }
        return result

    return {}


def extract_roi(performances: dict[str, dict], window: str) -> float:
    """Extract ROI for a specific window.

    Args:
        performances: Parsed performances dict from parse_window_performances.
        window: Window name ('day', 'week', 'month', 'year', 'allTime').

    Returns:
        ROI as decimal (e.g., 0.15 = 15%), or 0.0 if not found.
    """
    if window in performances:
        return float(performances[window].get("roi", 0) or 0)
    return 0.0


def extract_pnl(performances: dict[str, dict], window: str) -> float:
    """Extract PnL for a specific window.

    Args:
        performances: Parsed performances dict from parse_window_performances.
        window: Window name ('day', 'week', 'month', 'year', 'allTime').

    Returns:
        PnL in USD, or 0.0 if not found.
    """
    if window in performances:
        return float(performances[window].get("pnl", 0) or 0)
    return 0.0


def extract_volume(performances: dict[str, dict], window: str) -> float:
    """Extract volume for a specific window.

    Args:
        performances: Parsed performances dict from parse_window_performances.
        window: Window name ('day', 'week', 'month', 'year', 'allTime').

    Returns:
        Volume in USD, or 0.0 if not found.
    """
    if window in performances:
        return float(performances[window].get("vlm", 0) or 0)
    return 0.0


def is_positive_roi(performances: dict[str, dict], *windows: str) -> bool:
    """Check if ROI is positive for all specified windows.

    Args:
        performances: Parsed performances dict.
        *windows: Window names to check.

    Returns:
        True if all specified windows have positive ROI.
    """
    for window in windows:
        if extract_roi(performances, window) <= 0:
            return False
    return True
