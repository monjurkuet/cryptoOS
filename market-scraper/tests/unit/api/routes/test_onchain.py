# tests/unit/api/routes/test_onchain.py

"""Tests for on-chain API routes."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.routes.onchain import router
from market_scraper.core.events import StandardEvent


def _event(payload: dict) -> StandardEvent:
    """Build a generic event wrapper for route tests."""
    return StandardEvent.create(event_type="custom", source="test", payload=payload)


def _build_connectors() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Create a full on-chain connector tuple."""
    return tuple(MagicMock() for _ in range(6))  # type: ignore[return-value]


@pytest.fixture
def app() -> FastAPI:
    """Create a minimal FastAPI app for the on-chain router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/onchain")
    return app


class TestOnchainRoutes:
    """Tests for on-chain route behavior."""

    def test_network_route_exposes_market_fields(self, app: FastAPI, monkeypatch) -> None:
        """The network route should return price and market cap fields."""
        blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow = _build_connectors()
        blockchain.get_current_metrics = AsyncMock(
            return_value=_event(
                {
                    "hash_rate_ghs": 800_000_000_000,
                    "difficulty": 123.45,
                    "block_height": 1_234_567,
                    "total_btc": 19_900_000.0,
                    "price_usd": 67_295.0,
                    "market_cap_usd": 1_340_000_000_000.0,
                }
            )
        )

        async def fake_get_all_connectors():
            return (blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow)

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/btc/network")

            assert response.status_code == 200
            data = response.json()
            assert data["price_usd"] == 67_295.0
            assert data["market_cap_usd"] == 1_340_000_000_000.0

        asyncio.run(run_test())

    def test_activity_route_returns_expanded_coin_metrics(self, app: FastAPI, monkeypatch) -> None:
        """The activity route should expose the expanded Coin Metrics payload."""
        blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow = _build_connectors()
        coin_metrics.get_latest_metrics = AsyncMock(
            return_value=_event(
                {
                    "timestamp": "2026-04-05T00:00:00+00:00",
                    "metrics": {
                        "PriceUSD": 67_295.0,
                        "CapMrktCurUSD": 1_340_000_000_000.0,
                        "AdrActCnt": 500_000.0,
                        "TxCnt": 300_000.0,
                        "BlkCnt": 140.0,
                        "SplyCur": 19_900_000.0,
                    },
                }
            )
        )

        async def fake_get_all_connectors():
            return (blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow)

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/btc/activity")

            assert response.status_code == 200
            data = response.json()
            assert data["metrics"]["PriceUSD"] == 67_295.0
            assert data["metrics"]["CapMrktCurUSD"] == 1_340_000_000_000.0

        asyncio.run(run_test())

    def test_summary_falls_back_to_activity_market_fields(self, app: FastAPI, monkeypatch) -> None:
        """Summary should use activity data when network price fields are unavailable."""
        blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow = _build_connectors()
        blockchain.get_current_metrics = AsyncMock(side_effect=RuntimeError("network down"))
        fear_greed.get_current_index = AsyncMock(
            return_value=_event({"value": 55, "classification": "Neutral"})
        )
        coin_metrics.get_latest_metrics = AsyncMock(
            return_value=_event(
                {
                    "metrics": {
                        "PriceUSD": 67_295.0,
                        "CapMrktCurUSD": 1_340_000_000_000.0,
                        "AdrActCnt": 500_000.0,
                        "TxCnt": 300_000.0,
                        "SplyCur": 19_900_000.0,
                    }
                }
            )
        )
        cbbi.get_current_index = AsyncMock(
            return_value=_event({"confidence": 0.28, "price": 67_100.0, "components": {"MVRV": 1.5}})
        )
        bitview.get_summary = AsyncMock(
            return_value={
                "sopr": {"value": 1.02, "interpretation": "profit_taking"},
                "sopr_sth": {"value": 0.98},
                "sopr_lth": {"value": 1.05},
            }
        )
        exchange_flow.get_current_flows = AsyncMock(
            return_value=_event(
                {
                    "flow_in_btc": 1_000.0,
                    "flow_out_btc": 2_000.0,
                    "netflow_btc": 1_000.0,
                    "supply_btc": 2_500_000.0,
                    "netflow_interpretation": "bullish",
                }
            )
        )

        async def fake_get_all_connectors():
            return (blockchain, fear_greed, coin_metrics, cbbi, bitview, exchange_flow)

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/btc/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["price_usd"] == 67_295.0
            assert data["market_cap_usd"] == 1_340_000_000_000.0
            assert data["sentiment"]["cbbi_confidence"] == 0.28

        asyncio.run(run_test())

    def test_health_route_reports_healthy_when_all_sources_are_healthy(
        self, app: FastAPI, monkeypatch
    ) -> None:
        """All healthy connectors should produce an overall healthy status."""
        connectors = _build_connectors()
        for connector in connectors:
            connector.health_check = AsyncMock(return_value={"status": "healthy", "latency_ms": 1.0})

        async def fake_get_all_connectors():
            return connectors

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/health")

            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

        asyncio.run(run_test())

    def test_health_route_reports_degraded_on_partial_failure(
        self, app: FastAPI, monkeypatch
    ) -> None:
        """A single connector failure should degrade the overall health."""
        connectors = _build_connectors()
        for connector in connectors:
            connector.health_check = AsyncMock(return_value={"status": "healthy", "latency_ms": 1.0})
        connectors[2].health_check = AsyncMock(return_value={"status": "unhealthy", "message": "down"})

        async def fake_get_all_connectors():
            return connectors

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["connectors"]["coin_metrics"]["status"] == "unhealthy"

        asyncio.run(run_test())

    def test_health_route_reports_unhealthy_when_all_sources_fail(
        self, app: FastAPI, monkeypatch
    ) -> None:
        """All connector failures should produce an unhealthy status."""
        connectors = _build_connectors()
        for connector in connectors:
            connector.health_check = AsyncMock(return_value={"status": "unhealthy", "message": "down"})

        async def fake_get_all_connectors():
            return connectors

        monkeypatch.setattr("market_scraper.api.routes.onchain.get_all_connectors", fake_get_all_connectors)

        async def run_test() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/api/v1/onchain/health")

            assert response.status_code == 200
            assert response.json()["status"] == "unhealthy"

        asyncio.run(run_test())
