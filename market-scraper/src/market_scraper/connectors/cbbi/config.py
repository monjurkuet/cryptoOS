# src/market_scraper/connectors/cbbi/config.py

"""Configuration for the CBBI connector."""

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class CBBIConfig(ConnectorConfig):
    """Configuration for the CBBI (Colin Talks Crypto Bitcoin Index) connector.

    CBBI is a sentiment index that aggregates various Bitcoin metrics to provide
    a comprehensive market sentiment indicator.

    Attributes:
        base_url: Base URL for CBBI API endpoints
        api_key: Optional API key for premium features
        update_interval_seconds: How often to fetch new data
        historical_days: Number of days of historical data to fetch
        metrics_enabled: Whether to emit Prometheus metrics
    """

    base_url: HttpUrl = Field(
        default="https://colintalkscrypto.com/cbbi/data",
        description="Base URL for CBBI API endpoints",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for premium features",
    )
    update_interval_seconds: int = Field(
        default=86400,  # 24 hours - CBBI updates daily
        ge=60,
        le=86400,
        description="How often to fetch new data (in seconds, min: 60, max: 86400)",
    )
    historical_days: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Number of days of historical data to fetch (default: 365)",
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Whether to emit Prometheus metrics",
    )

    model_config = {"extra": "allow"}
