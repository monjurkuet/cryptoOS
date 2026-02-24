# src/market_scraper/connectors/bitview/__init__.py

"""Bitview.space connector for Bitcoin on-chain metrics.

This connector provides access to free Bitcoin on-chain metrics from
Bitview.space, which is a hosted instance of Bitcoin Research Kit (BRK).

No API key required. No rate limits. Data computed from live Bitcoin node.

Example usage:
    from market_scraper.connectors.bitview import (
        BitviewConnector,
        BitviewConfig,
        BitviewMetric,
    )

    async def main():
        config = BitviewConfig(name="bitview")
        connector = BitviewConnector(config)
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
        print(f"NUPL: {nupl.payload['value_normalized']}")
        print(f"Zone: {nupl.payload['zone']}")

        # Get MVRV
        mvrv = await connector.get_mvrv()
        print(f"MVRV: {mvrv.payload['value']}")
        print(f"Signal: {mvrv.payload['signal']}")

        # Get summary
        summary = await connector.get_summary()
        print(f"Summary: {summary}")

        await connector.disconnect()
"""

from market_scraper.connectors.bitview.client import BitviewClient
from market_scraper.connectors.bitview.config import BitviewConfig, BitviewMetric
from market_scraper.connectors.bitview.connector import BitviewConnector
from market_scraper.connectors.bitview.parsers import (
    parse_bitview_liveliness,
    parse_bitview_metric,
    parse_bitview_mvrv,
    parse_bitview_nupl,
    parse_bitview_puell,
    parse_bitview_realized_cap,
    parse_bitview_realized_price,
    parse_bitview_sopr,
    validate_bitview_data,
)

__all__ = [
    "BitviewConnector",
    "BitviewConfig",
    "BitviewClient",
    "BitviewMetric",
    "parse_bitview_metric",
    "parse_bitview_sopr",
    "parse_bitview_nupl",
    "parse_bitview_mvrv",
    "parse_bitview_liveliness",
    "parse_bitview_realized_cap",
    "parse_bitview_realized_price",
    "parse_bitview_puell",
    "validate_bitview_data",
]
