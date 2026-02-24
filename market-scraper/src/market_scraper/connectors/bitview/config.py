# src/market_scraper/connectors/bitview/config.py

"""Configuration for the Bitview (BRK) connector."""

from enum import StrEnum

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class BitviewMetric(StrEnum):
    """Available metrics from Bitview.space API (Bitcoin Research Kit)."""

    # SOPR metrics
    SOPR = "sopr"
    SOPR_LTH = "lth_sopr"
    SOPR_STH = "sth_sopr"

    # NUPL metrics
    NUPL = "nupl"
    NUPL_LTH = "lth_nupl"
    NUPL_STH = "sth_nupl"

    # MVRV metrics
    MVRV = "mvrv"
    MVRV_LTH = "lth_mvrv"
    MVRV_STH = "sth_mvrv"

    # Realized metrics
    REALIZED_CAP = "realized_cap"
    REALIZED_PRICE = "realized_price"

    # Other on-chain metrics
    LIVELINESS = "liveliness"
    PUELL_MULTIPLE = "puell_multiple"
    THERMO_CAP = "thermo_cap"
    COINTIME_CAP = "cointime_cap"

    # Price metrics
    PRICE_CLOSE = "price_close"


class BitviewConfig(ConnectorConfig):
    """Configuration for the Bitview connector.

    Bitview.space is a free hosted instance of Bitcoin Research Kit (BRK),
    providing Bitcoin on-chain metrics computed from a live Bitcoin node.

    No API key required. No rate limits.

    Attributes:
        base_url: Base URL for Bitview API
        update_interval_seconds: How often to fetch new data (daily recommended)
        cache_ttl_seconds: Cache time-to-live in seconds
        metrics: List of metrics to enable
    """

    base_url: HttpUrl = Field(
        default="https://bitview.space/api",
        description="Base URL for Bitview API",
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
            BitviewMetric.SOPR.value,
            BitviewMetric.SOPR_LTH.value,
            BitviewMetric.SOPR_STH.value,
            BitviewMetric.NUPL.value,
            BitviewMetric.MVRV.value,
            BitviewMetric.LIVELINESS.value,
        ],
        description="List of metrics to fetch",
    )

    model_config = {"extra": "allow"}
