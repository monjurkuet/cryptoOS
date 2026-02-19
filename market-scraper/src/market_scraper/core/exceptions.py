# src/market_scraper/core/exceptions.py

"""Custom exceptions for the Market Scraper Framework."""


class MarketScraperError(Exception):
    """Base exception for all market scraper errors."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize the exception with a message."""
        super().__init__(message, *args)
        self.message = message


class EventBusError(MarketScraperError):
    """Exception raised for event bus related errors."""

    pass


class DataFetchError(MarketScraperError):
    """Exception raised when data fetching fails."""

    pass


class ValidationError(MarketScraperError):
    """Exception raised when data validation fails."""

    pass


class ConfigurationError(MarketScraperError):
    """Exception raised for configuration errors."""

    pass


class StorageError(MarketScraperError):
    """Exception raised for storage related errors."""

    pass


class ConnectorError(MarketScraperError):
    """Exception raised for connector related errors."""

    pass
