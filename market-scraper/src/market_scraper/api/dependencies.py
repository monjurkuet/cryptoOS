# src/market_scraper/api/dependencies.py

"""FastAPI dependency injection for API routes.

This module provides dependency injection functions for:
- Lifecycle manager
- Settings
- On-chain data connectors (via ConnectorRegistry)
"""

from functools import lru_cache
from typing import Any

import structlog
from fastapi import Request

from market_scraper.connectors.registry import ConnectorRegistry
from market_scraper.core.config import Settings, get_settings
from market_scraper.orchestration.lifecycle import LifecycleManager

logger = structlog.get_logger(__name__)


def get_lifecycle(request: Request) -> LifecycleManager:
    """Get lifecycle manager from app state."""
    return request.app.state.lifecycle


def get_settings_dependency() -> Settings:
    """Get application settings."""
    return get_settings()


# ============== Connector Factory using Registry ==============


# Mapping from friendly names to registry names and config classes
CONNECTOR_MAPPING: dict[str, tuple[str, type, type]] = {
    "blockchain_info": (
        "blockchain_info",
        "market_scraper.connectors.blockchain_info",
    ),
    "fear_greed": (
        "fear_greed",
        "market_scraper.connectors.fear_greed",
    ),
    "coin_metrics": (
        "coin_metrics",
        "market_scraper.connectors.coin_metrics",
    ),
    "cbbi": (
        "cbbi",
        "market_scraper.connectors.cbbi",
    ),
    "chainexposed": (
        "chainexposed",
        "market_scraper.connectors.chainexposed",
    ),
    "exchange_flow": (
        "exchange_flow",
        "market_scraper.connectors.exchange_flow",
    ),
}


class ConnectorFactory:
    """Factory for creating and caching on-chain data connectors.

    Uses ConnectorRegistry for dynamic connector discovery.
    Provides thread-safe singleton connectors via caching.
    Each connector is initialized lazily on first access.
    """

    def __init__(self) -> None:
        """Initialize the factory with empty connector cache."""
        self._connectors: dict[str, Any] = {}
        self._connector_configs: dict[str, type] = {}

    def _load_connector_config(self, name: str) -> type:
        """Load connector config class dynamically.

        Args:
            name: Connector name

        Returns:
            Connector config class
        """
        if name in self._connector_configs:
            return self._connector_configs[name]

        # Import and cache config class
        if name == "blockchain_info":
            from market_scraper.connectors.blockchain_info import BlockchainInfoConfig

            self._connector_configs[name] = BlockchainInfoConfig
        elif name == "fear_greed":
            from market_scraper.connectors.fear_greed import FearGreedConfig

            self._connector_configs[name] = FearGreedConfig
        elif name == "coin_metrics":
            from market_scraper.connectors.coin_metrics import CoinMetricsConfig

            self._connector_configs[name] = CoinMetricsConfig
        elif name == "cbbi":
            from market_scraper.connectors.cbbi import CBBIConfig

            self._connector_configs[name] = CBBIConfig
        elif name == "chainexposed":
            from market_scraper.connectors.chainexposed import ChainExposedConfig

            self._connector_configs[name] = ChainExposedConfig
        elif name == "exchange_flow":
            from market_scraper.connectors.exchange_flow import ExchangeFlowConfig

            self._connector_configs[name] = ExchangeFlowConfig
        else:
            from market_scraper.connectors.base import ConnectorConfig

            self._connector_configs[name] = ConnectorConfig

        return self._connector_configs[name]

    async def get_connector(self, name: str) -> Any:
        """Get or create a connector by name.

        Args:
            name: Connector name (e.g., "blockchain_info", "cbbi")

        Returns:
            Connector instance
        """
        if name in self._connectors:
            return self._connectors[name]

        # Get connector class from registry
        try:
            connector_class = ConnectorRegistry.get(name)
        except KeyError:
            logger.error("connector_not_in_registry", name=name)
            raise ValueError(f"Connector '{name}' not found in registry")

        # Get config class
        config_class = self._load_connector_config(name)
        config = config_class(name=name)

        # Create and connect
        connector = connector_class(config)
        await connector.connect()

        self._connectors[name] = connector
        logger.info("connector_created", name=name)
        return connector

    async def get_blockchain_connector(self) -> Any:
        """Get or create BlockchainInfoConnector."""
        return await self.get_connector("blockchain_info")

    async def get_fear_greed_connector(self) -> Any:
        """Get or create FearGreedConnector."""
        return await self.get_connector("fear_greed")

    async def get_coin_metrics_connector(self) -> Any:
        """Get or create CoinMetricsConnector."""
        return await self.get_connector("coin_metrics")

    async def get_cbbi_connector(self) -> Any:
        """Get or create CBBIConnector."""
        return await self.get_connector("cbbi")

    async def get_chainexposed_connector(self) -> Any:
        """Get or create ChainExposedConnector."""
        return await self.get_connector("chainexposed")

    async def get_exchange_flow_connector(self) -> Any:
        """Get or create ExchangeFlowConnector."""
        return await self.get_connector("exchange_flow")

    async def get_all_connectors(self) -> tuple:
        """Get all connectors as a tuple.

        Returns connectors in the order expected by onchain.py routes:
        (blockchain, fear_greed, coin_metrics, cbbi, chainexposed, exchange_flow)
        """
        return (
            await self.get_blockchain_connector(),
            await self.get_fear_greed_connector(),
            await self.get_coin_metrics_connector(),
            await self.get_cbbi_connector(),
            await self.get_chainexposed_connector(),
            await self.get_exchange_flow_connector(),
        )

    async def close_all(self) -> None:
        """Close all connectors."""
        for name, connector in self._connectors.items():
            if hasattr(connector, "disconnect"):
                try:
                    await connector.disconnect()
                except Exception as e:
                    logger.debug("connector_disconnect_error", connector=name, error=str(e))
        self._connectors.clear()
        logger.info("all_connectors_closed")


@lru_cache
def get_connector_factory() -> ConnectorFactory:
    """Get or create the singleton ConnectorFactory.

    Uses lru_cache for thread-safe singleton pattern.
    """
    return ConnectorFactory()


# ============== FastAPI Dependencies ==============


async def get_blockchain_connector() -> Any:
    """FastAPI dependency for BlockchainInfoConnector."""
    factory = get_connector_factory()
    return await factory.get_blockchain_connector()


async def get_fear_greed_connector() -> Any:
    """FastAPI dependency for FearGreedConnector."""
    factory = get_connector_factory()
    return await factory.get_fear_greed_connector()


async def get_coin_metrics_connector() -> Any:
    """FastAPI dependency for CoinMetricsConnector."""
    factory = get_connector_factory()
    return await factory.get_coin_metrics_connector()


async def get_cbbi_connector() -> Any:
    """FastAPI dependency for CBBIConnector."""
    factory = get_connector_factory()
    return await factory.get_cbbi_connector()


async def get_chainexposed_connector() -> Any:
    """FastAPI dependency for ChainExposedConnector."""
    factory = get_connector_factory()
    return await factory.get_chainexposed_connector()


async def get_exchange_flow_connector() -> Any:
    """FastAPI dependency for ExchangeFlowConnector."""
    factory = get_connector_factory()
    return await factory.get_exchange_flow_connector()


async def get_all_connectors() -> tuple:
    """FastAPI dependency for all connectors."""
    factory = get_connector_factory()
    return await factory.get_all_connectors()
