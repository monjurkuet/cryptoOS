# src/market_scraper/api/dependencies.py

"""FastAPI dependency injection for API routes.

This module provides dependency injection functions for:
- Lifecycle manager
- Settings
- On-chain data connectors
"""

from functools import lru_cache
from typing import Any

from fastapi import Request

from market_scraper.core.config import Settings, get_settings
from market_scraper.orchestration.lifecycle import LifecycleManager


def get_lifecycle(request: Request) -> LifecycleManager:
    """Get lifecycle manager from app state."""
    return request.app.state.lifecycle


def get_settings_dependency() -> Settings:
    """Get application settings."""
    return get_settings()


# ============== Connector Factory ==============

class ConnectorFactory:
    """Factory for creating and caching on-chain data connectors.

    Provides thread-safe singleton connectors via caching.
    Each connector is initialized lazily on first access.
    """

    def __init__(self) -> None:
        """Initialize the factory with empty connector cache."""
        self._connectors: dict[str, Any] = {}

    async def get_blockchain_connector(self) -> Any:
        """Get or create BlockchainInfoConnector."""
        if "blockchain_info" not in self._connectors:
            from market_scraper.connectors.blockchain_info import (
                BlockchainInfoConnector,
                BlockchainInfoConfig,
            )
            self._connectors["blockchain_info"] = BlockchainInfoConnector(
                BlockchainInfoConfig(name="blockchain_info")
            )
            await self._connectors["blockchain_info"].connect()
        return self._connectors["blockchain_info"]

    async def get_fear_greed_connector(self) -> Any:
        """Get or create FearGreedConnector."""
        if "fear_greed" not in self._connectors:
            from market_scraper.connectors.fear_greed import (
                FearGreedConnector,
                FearGreedConfig,
            )
            self._connectors["fear_greed"] = FearGreedConnector(
                FearGreedConfig(name="fear_greed")
            )
            await self._connectors["fear_greed"].connect()
        return self._connectors["fear_greed"]

    async def get_coin_metrics_connector(self) -> Any:
        """Get or create CoinMetricsConnector."""
        if "coin_metrics" not in self._connectors:
            from market_scraper.connectors.coin_metrics import (
                CoinMetricsConnector,
                CoinMetricsConfig,
            )
            self._connectors["coin_metrics"] = CoinMetricsConnector(
                CoinMetricsConfig(name="coin_metrics")
            )
            await self._connectors["coin_metrics"].connect()
        return self._connectors["coin_metrics"]

    async def get_cbbi_connector(self) -> Any:
        """Get or create CBBIConnector."""
        if "cbbi" not in self._connectors:
            from market_scraper.connectors.cbbi import CBBIConnector, CBBIConfig
            self._connectors["cbbi"] = CBBIConnector(CBBIConfig(name="cbbi"))
            await self._connectors["cbbi"].connect()
        return self._connectors["cbbi"]

    async def get_chainexposed_connector(self) -> Any:
        """Get or create ChainExposedConnector."""
        if "chainexposed" not in self._connectors:
            from market_scraper.connectors.chainexposed import (
                ChainExposedConnector,
                ChainExposedConfig,
            )
            self._connectors["chainexposed"] = ChainExposedConnector(
                ChainExposedConfig(name="chainexposed")
            )
            await self._connectors["chainexposed"].connect()
        return self._connectors["chainexposed"]

    async def get_exchange_flow_connector(self) -> Any:
        """Get or create ExchangeFlowConnector."""
        if "exchange_flow" not in self._connectors:
            from market_scraper.connectors.exchange_flow import (
                ExchangeFlowConnector,
                ExchangeFlowConfig,
            )
            self._connectors["exchange_flow"] = ExchangeFlowConnector(
                ExchangeFlowConfig(name="exchange_flow")
            )
            await self._connectors["exchange_flow"].connect()
        return self._connectors["exchange_flow"]

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
                except Exception:
                    pass
        self._connectors.clear()


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
