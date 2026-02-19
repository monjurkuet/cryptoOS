# src/market_scraper/core/types.py

"""Type aliases and constants for the Market Scraper Framework."""

from typing import Literal, NewType

# Type aliases for domain concepts
Symbol = NewType("Symbol", str)
Timeframe = Literal["1s", "1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
ConnectorName = NewType("ConnectorName", str)
EventId = NewType("EventId", str)
CorrelationId = NewType("CorrelationId", str)

# Valid timeframes
VALID_TIMEFRAMES: list[Timeframe] = [
    "1s",
    "1m",
    "5m",
    "15m",
    "1h",
    "4h",
    "1d",
    "1w",
    "1M",
]
