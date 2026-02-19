# src/market_scraper/connectors/blockchain_info/__init__.py

"""Blockchain.info connector for Bitcoin network metrics.

This connector provides access to Bitcoin network data from Blockchain.info,
including hash rate, difficulty, transaction counts, and market data.

Example usage:
    from market_scraper.connectors.blockchain_info import (
        BlockchainInfoConnector,
        BlockchainInfoConfig,
        BlockchainChartType,
    )

    async def main():
        config = BlockchainInfoConfig(name="blockchain_info")
        connector = BlockchainInfoConnector(config)
        await connector.connect()

        # Get current network metrics
        metrics = await connector.get_current_metrics()
        print(f"Block height: {metrics.payload['block_height']}")
        print(f"Hash rate: {metrics.payload['hash_rate_ghs']} GH/s")

        # Get specific chart data
        hash_rate_chart = await connector.get_chart(
            BlockchainChartType.HASH_RATE,
            timespan="30days"
        )
        print(f"Latest hash rate: {hash_rate_chart.payload['value']} TH/s")

        await connector.disconnect()
"""

from market_scraper.connectors.blockchain_info.client import BlockchainInfoClient
from market_scraper.connectors.blockchain_info.config import (
    BlockchainChartType,
    BlockchainInfoConfig,
)
from market_scraper.connectors.blockchain_info.connector import BlockchainInfoConnector
from market_scraper.connectors.blockchain_info.parsers import (
    parse_chart_historical,
    parse_chart_response,
    parse_current_metrics,
    validate_chart_data,
)

__all__ = [
    "BlockchainInfoConnector",
    "BlockchainInfoConfig",
    "BlockchainInfoClient",
    "BlockchainChartType",
    "parse_chart_response",
    "parse_chart_historical",
    "parse_current_metrics",
    "validate_chart_data",
]
