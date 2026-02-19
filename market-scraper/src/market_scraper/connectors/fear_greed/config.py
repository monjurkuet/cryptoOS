# src/market_scraper/connectors/fear_greed/config.py

"""Configuration for the Fear & Greed Index connector."""

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class FearGreedConfig(ConnectorConfig):
    """Configuration for the Fear & Greed Index connector.

    The Fear & Greed Index from Alternative.me provides a sentiment
    indicator for the cryptocurrency market, ranging from 0 (Extreme Fear)
    to 100 (Extreme Greed).

    Attributes:
        base_url: Base URL for Fear & Greed API
        update_interval_seconds: How often to fetch new data
        historical_limit: Maximum number of historical entries to fetch
        date_format: Date format for responses ('us', 'cn', 'kr', 'world')
    """

    base_url: HttpUrl = Field(
        default="https://api.alternative.me/fng",
        description="Base URL for Fear & Greed Index API",
    )
    update_interval_seconds: int = Field(
        default=3600,  # 1 hour
        ge=60,
        le=86400,
        description="How often to fetch new data (in seconds)",
    )
    historical_limit: int = Field(
        default=0,  # 0 = all available
        ge=0,
        le=1000,
        description="Maximum historical entries (0 = all available)",
    )
    date_format: str = Field(
        default="world",
        description="Date format for responses ('us', 'cn', 'kr', 'world')",
    )

    model_config = {"extra": "allow"}
