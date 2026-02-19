"""Core module for Market Scraper Framework."""

from market_scraper.core.config import Settings, get_settings
from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.core.exceptions import (
    ConfigurationError,
    ConnectorError,
    DataFetchError,
    EventBusError,
    MarketScraperError,
    StorageError,
    ValidationError,
)
from market_scraper.core.types import (
    VALID_TIMEFRAMES,
    ConnectorName,
    CorrelationId,
    EventId,
    Symbol,
    Timeframe,
)

__all__ = [
    "EventType",
    "MarketDataPayload",
    "StandardEvent",
    "MarketScraperError",
    "EventBusError",
    "DataFetchError",
    "ValidationError",
    "ConfigurationError",
    "StorageError",
    "ConnectorError",
    "Symbol",
    "Timeframe",
    "ConnectorName",
    "EventId",
    "CorrelationId",
    "VALID_TIMEFRAMES",
    "Settings",
    "get_settings",
]
