# src/market_scraper/connectors/coin_metrics/config.py

"""Configuration for the Coin Metrics connector."""

from enum import StrEnum
from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class CoinMetricsMetric(StrEnum):
    """Available metrics from Coin Metrics Community API."""

    # Network activity metrics
    ACTIVE_ADDRESSES = "AdrActCnt"
    TRANSACTION_COUNT = "TxCnt"
    BLOCK_COUNT = "BlkCnt"

    # Supply metrics
    SUPPLY_CURRENT = "SplyCur"


class CoinMetricsConfig(ConnectorConfig):
    """Configuration for the Coin Metrics Community API connector.

    Provides access to Bitcoin metrics from Coin Metrics Community API,
    which offers free access to basic cryptocurrency metrics without
    requiring an API key.

    Note: Advanced metrics like MVRV, Realized Cap, etc. require a
    paid subscription.

    Attributes:
        base_url: Base URL for Coin Metrics Community API
        api_key: Optional API key for pro tier
        update_interval_seconds: How often to fetch new data
        asset: Default asset to fetch (e.g., 'btc')
        metrics: List of metrics to fetch
    """

    base_url: HttpUrl = Field(
        default="https://community-api.coinmetrics.io/v4",
        description="Base URL for Coin Metrics Community API",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for pro tier",
    )
    update_interval_seconds: int = Field(
        default=3600,  # 1 hour
        ge=60,
        le=86400,
        description="How often to fetch new data (in seconds)",
    )
    asset: str = Field(
        default="btc",
        description="Default asset to fetch",
    )
    metrics: list[str] = Field(
        default=[
            CoinMetricsMetric.ACTIVE_ADDRESSES.value,
            CoinMetricsMetric.TRANSACTION_COUNT.value,
            CoinMetricsMetric.BLOCK_COUNT.value,
            CoinMetricsMetric.SUPPLY_CURRENT.value,
        ],
        description="List of metrics to fetch",
    )

    model_config = {"extra": "allow"}
