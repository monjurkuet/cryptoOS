# src/market_scraper/connectors/chainexposed/config.py

"""Configuration for the ChainExposed connector."""

from enum import StrEnum

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class ChainExposedMetric(StrEnum):
    """Available metrics from ChainExposed.com."""

    # SOPR metrics
    SOPR = "SOPR"
    SOPR_LTH = "XthSOPRLongTermHolderCoin"  # Long-term holder SOPR
    SOPR_STH = "XthSOPRShortTermHolderCoin"  # Short-term holder SOPR

    # MVRV metrics
    MVRV = "MVRV"
    MVRV_LTH = "XthMVRVLongTermHolderAddress"
    MVRV_STH = "XthMVRVShortTermHolderAddress"

    # NUPL
    NUPL = "NUPL"

    # HODL Waves
    HODL_WAVES_ABSOLUTE = "HodlWavesAbsolute"
    HODL_WAVES_RELATIVE = "HodlWavesRelative"

    # Dormancy/CDD
    DORMANCY = "Dormancy"
    DORMANCY_FLOW = "DormancyFlow"

    # Activity
    ACTIVE_ADDRESSES = "ActiveAddresses"


class ChainExposedConfig(ConnectorConfig):
    """Configuration for the ChainExposed connector.

    ChainExposed.com provides free Bitcoin on-chain metrics by embedding
    data as JavaScript arrays in HTML pages. No API key required, no rate limits.

    Attributes:
        base_url: Base URL for ChainExposed pages
        update_interval_seconds: How often to fetch new data (daily recommended)
        cache_ttl_seconds: Cache time-to-live in seconds
        metrics: List of metrics to enable
    """

    base_url: HttpUrl = Field(
        default="https://chainexposed.com",
        description="Base URL for ChainExposed pages",
    )
    update_interval_seconds: int = Field(
        default=86400,  # 24 hours - data updates daily
        ge=3600,
        le=86400,
        description="How often to fetch new data (in seconds)",
    )
    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        ge=3600,
        description="Cache time-to-live in seconds",
    )
    metrics: list[str] = Field(
        default=[
            ChainExposedMetric.SOPR.value,
            ChainExposedMetric.SOPR_LTH.value,
            ChainExposedMetric.SOPR_STH.value,
            ChainExposedMetric.MVRV.value,
            ChainExposedMetric.NUPL.value,
            ChainExposedMetric.DORMANCY.value,
        ],
        description="List of metrics to fetch",
    )

    model_config = {"extra": "allow"}
