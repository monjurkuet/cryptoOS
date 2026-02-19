# src/market_scraper/connectors/exchange_flow/__init__.py

"""Exchange Flow connector for Bitcoin on-chain metrics.

This connector provides Bitcoin exchange flow data from Coin Metrics
Community CSV hosted on GitHub. No API key required. No rate limits.

Example usage:
    from market_scraper.connectors.exchange_flow import (
        ExchangeFlowConnector,
        ExchangeFlowConfig,
    )

    async def main():
        config = ExchangeFlowConfig(name="exchange_flow")
        connector = ExchangeFlowConnector(config)
        await connector.connect()

        # Get current flows
        flows = await connector.get_current_flows()
        print(f"Netflow: {flows.payload['netflow_btc']} BTC")
        print(f"Exchange Supply: {flows.payload['supply_btc']} BTC")
        print(f"Interpretation: {flows.payload['netflow_interpretation']}")

        # Get netflow summary
        summary = await connector.get_netflow_summary()
        print(f"7-day cumulative netflow: {summary['cumulative_netflow_7d']} BTC")

        await connector.disconnect()
"""

from market_scraper.connectors.exchange_flow.client import ExchangeFlowClient
from market_scraper.connectors.exchange_flow.config import ExchangeFlowConfig
from market_scraper.connectors.exchange_flow.connector import ExchangeFlowConnector
from market_scraper.connectors.exchange_flow.parsers import (
    parse_exchange_flow_data,
    parse_exchange_flow_summary,
    validate_exchange_flow_data,
)

__all__ = [
    "ExchangeFlowConnector",
    "ExchangeFlowConfig",
    "ExchangeFlowClient",
    "parse_exchange_flow_data",
    "parse_exchange_flow_summary",
    "validate_exchange_flow_data",
]
