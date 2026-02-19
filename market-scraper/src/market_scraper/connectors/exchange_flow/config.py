# src/market_scraper/connectors/exchange_flow/config.py

"""Configuration for the Exchange Flow connector."""

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class ExchangeFlowConfig(ConnectorConfig):
    """Configuration for the Exchange Flow connector.

    Fetches Bitcoin exchange flow data from Coin Metrics Community CSV.
    The CSV is updated daily and available for free without rate limits.

    Attributes:
        csv_url: URL to the Coin Metrics BTC CSV
        update_interval_seconds: How often to fetch new data
        cache_ttl_seconds: Cache time-to-live in seconds
    """

    csv_url: HttpUrl = Field(
        default="https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv",
        description="URL to Coin Metrics BTC CSV",
    )
    update_interval_seconds: int = Field(
        default=86400,  # 24 hours - CSV updates daily
        ge=3600,
        le=86400,
        description="How often to fetch new data (in seconds)",
    )
    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        ge=3600,
        description="Cache time-to-live in seconds",
    )

    model_config = {"extra": "allow"}
