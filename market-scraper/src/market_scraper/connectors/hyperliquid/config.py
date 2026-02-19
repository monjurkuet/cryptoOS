# src/market_scraper/connectors/hyperliquid/config.py

"""Hyperliquid connector configuration."""

from pydantic import Field

from market_scraper.connectors.base import ConnectorConfig


class HyperliquidConfig(ConnectorConfig):
    """Hyperliquid-specific configuration."""

    base_url: str = Field(
        default="https://api.hyperliquid.xyz",
        description="Base URL for Hyperliquid REST API",
    )
    ws_url: str = Field(
        default="wss://api.hyperliquid.xyz/ws",
        description="WebSocket URL for Hyperliquid streaming API",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for authenticated requests",
    )
