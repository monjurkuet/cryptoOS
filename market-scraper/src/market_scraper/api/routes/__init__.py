# src/market_scraper/api/routes/__init__.py

from market_scraper.api.routes import (
    cbbi,
    connectors,
    health,
    markets,
    onchain,
    signals,
    traders,
    websocket,
)

__all__ = [
    "health",
    "markets",
    "connectors",
    "traders",
    "signals",
    "cbbi",
    "onchain",
    "websocket",
]
