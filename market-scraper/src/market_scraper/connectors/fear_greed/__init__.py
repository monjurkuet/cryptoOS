# src/market_scraper/connectors/fear_greed/__init__.py

"""Fear & Greed Index connector for cryptocurrency market sentiment.

This connector provides access to the Alternative.me Fear & Greed Index,
a sentiment indicator for the cryptocurrency market.

Example usage:
    from market_scraper.connectors.fear_greed import (
        FearGreedConnector,
        FearGreedConfig,
    )

    async def main():
        config = FearGreedConfig(name="fear_greed")
        connector = FearGreedConnector(config)
        await connector.connect()

        # Get current index
        index = await connector.get_current_index()
        print(f"Fear & Greed: {index.payload['value']}")
        print(f"Classification: {index.payload['classification']}")

        # Get summary with statistics
        summary = await connector.get_summary(days=30)
        print(f"30-day average: {summary.payload['statistics']['average']}")

        await connector.disconnect()
"""

from market_scraper.connectors.fear_greed.client import FearGreedClient
from market_scraper.connectors.fear_greed.config import FearGreedConfig
from market_scraper.connectors.fear_greed.connector import FearGreedConnector
from market_scraper.connectors.fear_greed.parsers import (
    parse_fear_greed_historical,
    parse_fear_greed_response,
    parse_fear_greed_summary,
    validate_fear_greed_data,
)

__all__ = [
    "FearGreedConnector",
    "FearGreedConfig",
    "FearGreedClient",
    "parse_fear_greed_response",
    "parse_fear_greed_historical",
    "parse_fear_greed_summary",
    "validate_fear_greed_data",
]
