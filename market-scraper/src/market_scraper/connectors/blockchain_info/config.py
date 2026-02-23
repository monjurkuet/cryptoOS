# src/market_scraper/connectors/blockchain_info/config.py

"""Configuration for the Blockchain.info connector."""

from enum import StrEnum

from pydantic import Field, HttpUrl

from market_scraper.connectors.base import ConnectorConfig


class BlockchainChartType(StrEnum):
    """Available chart types from Blockchain.info API."""

    HASH_RATE = "hash-rate"
    DIFFICULTY = "difficulty"
    N_TRANSACTIONS = "n-transactions"
    N_UNIQUE_ADDRESSES = "n-unique-addresses"
    MARKET_PRICE = "market-price"
    MARKET_CAP = "market-cap"
    TOTAL_BITCOINS = "total-bitcoins"
    MEMPOOL_COUNT = "mempool-count"
    MEMPOOL_SIZE = "mempool-size"
    ESTIMATED_TRANSACTION_VOLUME_USD = "estimated-transaction-volume-usd"
    TRADE_VOLUME_USD = "trade-volume-usd"


class BlockchainInfoConfig(ConnectorConfig):
    """Configuration for the Blockchain.info connector.

    Provides access to Bitcoin network metrics including hash rate,
    difficulty, transaction counts, and market data.

    Attributes:
        base_url: Base URL for Blockchain.info Charts API
        query_url: Base URL for simple query API
        update_interval_seconds: How often to fetch new data
        default_timespan: Default timespan for chart data
        enabled_charts: List of charts to fetch
    """

    base_url: HttpUrl = Field(
        default="https://api.blockchain.info/charts",
        description="Base URL for Blockchain.info Charts API",
    )
    query_url: HttpUrl = Field(
        default="https://blockchain.info/q",
        description="Base URL for Blockchain.info simple query API",
    )
    update_interval_seconds: int = Field(
        default=3600,  # 1 hour
        ge=60,
        le=86400,
        description="How often to fetch new data (in seconds)",
    )
    default_timespan: str = Field(
        default="30days",
        description="Default timespan for chart data (e.g., '30days', '1year')",
    )
    enabled_charts: list[BlockchainChartType] = Field(
        default=[
            BlockchainChartType.HASH_RATE,
            BlockchainChartType.DIFFICULTY,
            BlockchainChartType.N_TRANSACTIONS,
            BlockchainChartType.N_UNIQUE_ADDRESSES,
            BlockchainChartType.MARKET_PRICE,
            BlockchainChartType.MARKET_CAP,
        ],
        description="List of charts to fetch",
    )
    cors_enabled: bool = Field(
        default=True,
        description="Enable CORS headers for cross-origin requests",
    )

    model_config = {"extra": "allow"}
