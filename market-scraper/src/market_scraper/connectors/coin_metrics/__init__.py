# src/market_scraper/connectors/coin_metrics/__init__.py

"""Coin Metrics Community API connector for Bitcoin metrics.

This connector provides access to Bitcoin metrics from Coin Metrics
Community API, which offers free access to basic metrics.

Example usage:
    from market_scraper.connectors.coin_metrics import (
        CoinMetricsConnector,
        CoinMetricsConfig,
        CoinMetricsMetric,
    )

    async def main():
        config = CoinMetricsConfig(name="coin_metrics")
        connector = CoinMetricsConnector(config)
        await connector.connect()

        # Get latest metrics
        metrics = await connector.get_latest_metrics()
        print(f"Price: ${metrics.payload['metrics']['PriceUSD']:,.2f}")
        print(f"Active Addresses: {metrics.payload['metrics']['AdrActCnt']:,}")

        # Get specific metric history
        price_history = await connector.get_metric_history(
            CoinMetricsMetric.PRICE_USD,
            days=30
        )
        print(f"30-day average: ${price_history.payload['statistics']['average']:,.2f}")

        await connector.disconnect()
"""

from market_scraper.connectors.coin_metrics.client import CoinMetricsClient
from market_scraper.connectors.coin_metrics.config import (
    CoinMetricsConfig,
    CoinMetricsMetric,
)
from market_scraper.connectors.coin_metrics.connector import CoinMetricsConnector
from market_scraper.connectors.coin_metrics.parsers import (
    parse_metrics_historical,
    parse_metrics_response,
    parse_single_metric,
    validate_metrics_data,
)

__all__ = [
    "CoinMetricsConnector",
    "CoinMetricsConfig",
    "CoinMetricsClient",
    "CoinMetricsMetric",
    "parse_metrics_response",
    "parse_metrics_historical",
    "parse_single_metric",
    "validate_metrics_data",
]
