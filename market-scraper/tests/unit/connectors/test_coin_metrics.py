# tests/unit/connectors/test_coin_metrics.py

"""Unit tests for Coin Metrics connector behavior."""

import asyncio

import httpx

from market_scraper.connectors.coin_metrics.client import CoinMetricsClient
from market_scraper.connectors.coin_metrics.config import CoinMetricsConfig, CoinMetricsMetric
from market_scraper.connectors.coin_metrics.parsers import parse_single_metric


class _DummyClient:
    """Minimal async HTTP client stub."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def get(self, url: str, params: dict[str, object] | None = None) -> httpx.Response:
        """Capture the request and return a JSON response."""
        self.calls.append({"url": url, "params": params or {}})
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json=self.payload, request=request)


class TestCoinMetricsConfig:
    """Tests for Coin Metrics defaults."""

    def test_default_metrics_include_price_and_market_cap(self) -> None:
        """The default metric set should include price and market cap."""
        config = CoinMetricsConfig(name="coin_metrics")

        assert config.metrics == [
            CoinMetricsMetric.PRICE_USD.value,
            CoinMetricsMetric.MARKET_CAP.value,
            CoinMetricsMetric.ACTIVE_ADDRESSES.value,
            CoinMetricsMetric.TRANSACTION_COUNT.value,
            CoinMetricsMetric.BLOCK_COUNT.value,
            CoinMetricsMetric.SUPPLY_CURRENT.value,
        ]


class TestCoinMetricsClient:
    """Tests for Coin Metrics client behavior."""

    def test_get_latest_metrics_uses_non_zero_day_window(self) -> None:
        """Latest-metrics requests should span more than one date."""
        payload = {
            "data": [
                {
                    "asset": "btc",
                    "time": "2026-04-05T00:00:00.000000000Z",
                    "PriceUSD": "70000",
                }
            ]
        }
        client = CoinMetricsClient(CoinMetricsConfig(name="coin_metrics"))
        client._client = _DummyClient(payload)

        asyncio.run(client.get_latest_metrics())

        params = client._client.calls[0]["params"]
        assert params["start_time"] != params["end_time"]
        assert params["frequency"] == "1d"

    def test_health_check_uses_canonical_metrics_probe(self) -> None:
        """Health checks should probe the canonical asset-metrics endpoint."""
        payload = {
            "data": [
                {
                    "asset": "btc",
                    "time": "2026-04-05T00:00:00.000000000Z",
                    "PriceUSD": "70000",
                    "CapMrktCurUSD": "1400000000000",
                    "AdrActCnt": "500000",
                    "TxCnt": "300000",
                    "BlkCnt": "140",
                    "SplyCur": "19900000",
                }
            ]
        }
        client = CoinMetricsClient(CoinMetricsConfig(name="coin_metrics"))
        client._client = _DummyClient(payload)

        health = asyncio.run(client.health_check())

        assert health["status"] == "healthy"
        params = client._client.calls[0]["params"]
        assert params["assets"] == "btc"
        assert params["frequency"] == "1d"
        assert params["metrics"].split(",") == [
            CoinMetricsMetric.PRICE_USD.value,
            CoinMetricsMetric.MARKET_CAP.value,
            CoinMetricsMetric.ACTIVE_ADDRESSES.value,
            CoinMetricsMetric.TRANSACTION_COUNT.value,
            CoinMetricsMetric.BLOCK_COUNT.value,
            CoinMetricsMetric.SUPPLY_CURRENT.value,
        ]


class TestCoinMetricsParsers:
    """Tests for Coin Metrics parser behavior."""

    def test_parse_single_metric_supports_price_metric_description(self) -> None:
        """The parser should understand PriceUSD descriptions."""
        event = parse_single_metric(
            {
                "data": [
                    {
                        "asset": "btc",
                        "time": "2026-04-05T00:00:00.000000000Z",
                        "PriceUSD": "70000",
                    }
                ]
            },
            CoinMetricsMetric.PRICE_USD.value,
        )

        assert event.payload["metric_name"] == CoinMetricsMetric.PRICE_USD.value
        assert event.payload["description"] == "Bitcoin price in USD"
