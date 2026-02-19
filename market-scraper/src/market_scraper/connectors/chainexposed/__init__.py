# src/market_scraper/connectors/chainexposed/__init__.py

"""ChainExposed.com connector for Bitcoin on-chain metrics.

This connector provides access to free Bitcoin on-chain metrics from
ChainExposed.com, which embeds data as JavaScript arrays in HTML pages.

No API key required. No rate limits.

Example usage:
    from market_scraper.connectors.chainexposed import (
        ChainExposedConnector,
        ChainExposedConfig,
        ChainExposedMetric,
    )

    async def main():
        config = ChainExposedConfig(name="chainexposed")
        connector = ChainExposedConnector(config)
        await connector.connect()

        # Get SOPR data
        sopr = await connector.get_sopr()
        print(f"SOPR: {sopr.payload['value']}")
        print(f"Interpretation: {sopr.payload['interpretation']}")

        # Get all SOPR variants
        all_sopr = await connector.get_all_sopr_metrics()
        print(f"STH-SOPR: {all_sopr['sth'].payload['value']}")

        # Get NUPL
        nupl = await connector.get_nupl()
        print(f"NUPL: {nupl.payload['value']}")
        print(f"Zone: {nupl.payload['zone']}")

        # Get summary
        summary = await connector.get_summary()
        print(f"Summary: {summary}")

        await connector.disconnect()
"""

from market_scraper.connectors.chainexposed.client import ChainExposedClient
from market_scraper.connectors.chainexposed.config import (
    ChainExposedConfig,
    ChainExposedMetric,
)
from market_scraper.connectors.chainexposed.connector import ChainExposedConnector
from market_scraper.connectors.chainexposed.parsers import (
    parse_chainexposed_dormancy,
    parse_chainexposed_hodl_waves,
    parse_chainexposed_metric,
    parse_chainexposed_mvrv,
    parse_chainexposed_nupl,
    parse_chainexposed_sopr,
    validate_chainexposed_data,
)

__all__ = [
    "ChainExposedConnector",
    "ChainExposedConfig",
    "ChainExposedClient",
    "ChainExposedMetric",
    "parse_chainexposed_metric",
    "parse_chainexposed_sopr",
    "parse_chainexposed_nupl",
    "parse_chainexposed_mvrv",
    "parse_chainexposed_dormancy",
    "parse_chainexposed_hodl_waves",
    "validate_chainexposed_data",
]
