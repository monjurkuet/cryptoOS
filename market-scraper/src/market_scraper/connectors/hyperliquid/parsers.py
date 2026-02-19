# src/market_scraper/connectors/hyperliquid/parsers.py

"""Parsers for Hyperliquid API responses."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent


def parse_trade(data: dict[str, Any], source: str) -> StandardEvent | None:
    """Parse trade data from Hyperliquid WebSocket.

    Args:
        data: Raw trade data from WebSocket
        source: Source identifier (e.g., "hyperliquid")

    Returns:
        StandardEvent if parsing succeeds, None otherwise
    """
    try:
        trades = data.get("data", [])
        if not trades:
            return None

        # Take the first trade if multiple
        trade = trades[0] if isinstance(trades, list) else trades

        # Validate required fields exist
        if "px" not in trade or "sz" not in trade or "coin" not in trade:
            return None

        payload = MarketDataPayload(
            symbol=trade.get("coin", ""),
            price=float(trade["px"]),
            volume=float(trade["sz"]),
            timestamp=datetime.utcnow(),
        )

        return StandardEvent.create(
            event_type=EventType.TRADE,
            source=source,
            payload=payload.model_dump(),
        )
    except (KeyError, ValueError, TypeError):
        return None


def parse_orderbook(data: dict[str, Any], source: str) -> StandardEvent | None:
    """Parse order book data from Hyperliquid WebSocket.

    Args:
        data: Raw order book data from WebSocket
        source: Source identifier (e.g., "hyperliquid")

    Returns:
        StandardEvent if parsing succeeds, None otherwise
    """
    try:
        coin = data.get("data", {}).get("coin", "")
        levels = data.get("data", {}).get("levels", [[], []])

        if not levels or len(levels) < 2:
            return None

        bids = levels[0]
        asks = levels[1]

        best_bid = bids[0] if bids else None
        best_ask = asks[0] if asks else None

        payload = MarketDataPayload(
            symbol=coin,
            bid=float(best_bid["px"]) if best_bid else None,
            bid_volume=float(best_bid["sz"]) if best_bid else None,
            ask=float(best_ask["px"]) if best_ask else None,
            ask_volume=float(best_ask["sz"]) if best_ask else None,
            timestamp=datetime.utcnow(),
        )

        return StandardEvent.create(
            event_type=EventType.ORDER_BOOK,
            source=source,
            payload=payload.model_dump(),
        )
    except (KeyError, ValueError, TypeError):
        return None


def parse_ticker(data: dict[str, Any], source: str) -> StandardEvent | None:
    """Parse ticker data from Hyperliquid WebSocket.

    Args:
        data: Raw ticker data from WebSocket
        source: Source identifier (e.g., "hyperliquid")

    Returns:
        StandardEvent if parsing succeeds, None otherwise
    """
    try:
        ticker_data = data.get("data", {})
        coin = ticker_data.get("coin", "")

        payload = MarketDataPayload(
            symbol=coin,
            price=float(ticker_data.get("markPrice", 0)) or None,
            timestamp=datetime.utcnow(),
        )

        return StandardEvent.create(
            event_type=EventType.TICKER,
            source=source,
            payload=payload.model_dump(),
        )
    except (KeyError, ValueError, TypeError):
        return None


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
