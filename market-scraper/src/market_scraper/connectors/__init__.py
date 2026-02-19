# src/market_scraper/connectors/__init__.py

"""Connectors module for market data sources."""

from market_scraper.connectors.base import ConnectorConfig, DataConnector
from market_scraper.connectors.registry import ConnectorRegistry

# Auto-register connectors when module is imported
from market_scraper.connectors.hyperliquid import HyperliquidConnector
from market_scraper.connectors.cbbi import CBBIConnector
from market_scraper.connectors.blockchain_info import BlockchainInfoConnector
from market_scraper.connectors.fear_greed import FearGreedConnector
from market_scraper.connectors.coin_metrics import CoinMetricsConnector

ConnectorRegistry.register("hyperliquid", HyperliquidConnector)
ConnectorRegistry.register("cbbi", CBBIConnector)
ConnectorRegistry.register("blockchain_info", BlockchainInfoConnector)
ConnectorRegistry.register("fear_greed", FearGreedConnector)
ConnectorRegistry.register("coin_metrics", CoinMetricsConnector)

__all__ = [
    "ConnectorConfig",
    "DataConnector",
    "ConnectorRegistry",
    "HyperliquidConnector",
    "CBBIConnector",
    "BlockchainInfoConnector",
    "FearGreedConnector",
    "CoinMetricsConnector",
]
