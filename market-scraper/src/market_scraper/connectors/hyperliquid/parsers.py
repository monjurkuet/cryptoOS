# src/market_scraper/connectors/hyperliquid/parsers.py

"""Parsers for Hyperliquid API responses."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent


def parse_candle(data: dict[str, Any], source: str, symbol: str) -> StandardEvent | None:
    """Parse candle data from Hyperliquid REST API.

    Args:
        data: Raw candle data from API
        source: Source identifier (e.g., "hyperliquid")
        symbol: Trading symbol

    Returns:
        StandardEvent if parsing succeeds, None otherwise
    """
    try:
        payload = MarketDataPayload(
            symbol=symbol,
            open=float(data.get("o", 0)),
            high=float(data.get("h", 0)),
            low=float(data.get("l", 0)),
            close=float(data.get("c", 0)),
            volume=float(data.get("v", 0)),
            timestamp=datetime.fromtimestamp(data.get("t", 0) / 1000),
        )

        return StandardEvent.create(
            event_type=EventType.OHLCV,
            source=source,
            payload=payload.model_dump(),
        )
    except (KeyError, ValueError, TypeError):
        return None
