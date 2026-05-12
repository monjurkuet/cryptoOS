"""Tests for the read-only Binance account client."""

from __future__ import annotations

import json

import httpx
import pytest

from market_scraper.binance_account.client import BinanceAccountClient, BinanceCredentials
from market_scraper.core.config import BinanceAccountSettings


@pytest.mark.asyncio
async def test_get_positions_normalizes_spot_and_futures() -> None:
    """Client returns combined spot balances, futures positions, and totals."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in {"/api/v3/time", "/fapi/v1/time"}:
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        if path == "/api/v3/account":
            return httpx.Response(
                200,
                json={
                    "balances": [
                        {"asset": "BTC", "free": "0.1", "locked": "0"},
                        {"asset": "USDT", "free": "25", "locked": "5"},
                        {"asset": "EMPTY", "free": "0", "locked": "0"},
                    ]
                },
            )
        if path == "/api/v3/ticker/price":
            return httpx.Response(200, json=[{"symbol": "BTCUSDT", "price": "100000"}])
        if path == "/fapi/v3/account":
            return httpx.Response(
                200,
                json={"totalWalletBalance": "1000", "totalUnrealizedProfit": "12.5"},
            )
        if path == "/fapi/v3/positionRisk":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "positionAmt": "0.2",
                        "entryPrice": "90000",
                        "markPrice": "100000",
                        "notional": "20000",
                        "unRealizedProfit": "2000",
                        "leverage": "5",
                        "marginType": "isolated",
                        "liquidationPrice": "75000",
                    },
                    {"symbol": "ETHUSDT", "positionAmt": "0", "markPrice": "3000"},
                ],
            )
        raise AssertionError(f"unexpected path {path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BinanceAccountClient(
            BinanceCredentials(api_key="key", api_secret="secret"),
            BinanceAccountSettings(
                spot_base_url="https://api.binance.test",
                futures_base_url="https://fapi.binance.test",
            ),
            http_client=http_client,
        )
        result = await client.get_positions("conn_1")

    assert result.connection_id == "conn_1"
    assert result.totals.spot_value_usdt == 10030
    assert result.totals.futures_wallet_balance_usdt == 1000
    assert result.totals.futures_unrealized_pnl_usdt == 12.5
    assert result.spot_balances[0].asset == "BTC"
    assert len(result.futures_positions) == 1
    assert result.futures_positions[0].side == "long"


@pytest.mark.asyncio
async def test_signed_request_retries_timestamp_drift() -> None:
    """Binance timestamp drift errors trigger one time-sync retry."""
    attempts = {"account": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in {"/api/v3/time", "/fapi/v1/time"}:
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        if path == "/api/v3/account":
            attempts["account"] += 1
            if attempts["account"] == 1:
                return httpx.Response(400, json={"code": -1021, "msg": "Timestamp outside"})
            return httpx.Response(200, json={"balances": []})
        if path == "/api/v3/ticker/price":
            return httpx.Response(200, json=[])
        if path == "/fapi/v3/account":
            return httpx.Response(
                200,
                json={"totalWalletBalance": "0", "totalUnrealizedProfit": "0"},
            )
        if path == "/fapi/v3/positionRisk":
            return httpx.Response(200, json=[])
        raise AssertionError(json.dumps({"unexpected": path}))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = BinanceAccountClient(
            BinanceCredentials(api_key="key", api_secret="secret"),
            BinanceAccountSettings(
                spot_base_url="https://api.binance.test",
                futures_base_url="https://fapi.binance.test",
            ),
            http_client=http_client,
        )
        result = await client.get_positions("conn_1")

    assert result.warnings == ["Binance timestamp drift detected; request retried"]
    assert attempts["account"] == 2
