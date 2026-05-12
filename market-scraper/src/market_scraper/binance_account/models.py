"""Pydantic models for Binance saved-account APIs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class BinanceAccountScope(StrEnum):
    """Supported saved Binance account scopes."""

    SPOT_AND_USDM_FUTURES = "spot_and_usdm_futures"


class BinanceConnectionCreateRequest(BaseModel):
    """Request to save a Binance API key and secret."""

    label: str = Field(min_length=1, max_length=80)
    api_key: str = Field(min_length=8, max_length=512)
    api_secret: str = Field(min_length=8, max_length=512)
    scope: BinanceAccountScope = BinanceAccountScope.SPOT_AND_USDM_FUTURES


class BinanceConnectionResponse(BaseModel):
    """Saved Binance connection metadata."""

    connection_id: str
    label: str
    scope: BinanceAccountScope
    masked_api_key: str
    created_at: datetime
    updated_at: datetime


class BinanceConnectionsListResponse(BaseModel):
    """Saved Binance connections list response."""

    connections: list[BinanceConnectionResponse]


class BinanceTotalsResponse(BaseModel):
    """Portfolio-level Binance totals."""

    estimated_usdt_value: float
    spot_value_usdt: float
    futures_wallet_balance_usdt: float
    futures_unrealized_pnl_usdt: float


class SpotBalanceResponse(BaseModel):
    """Nonzero Binance spot balance with best-effort USDT valuation."""

    asset: str
    free: float
    locked: float
    total: float
    price_usdt: float | None = None
    value_usdt: float | None = None


class FuturesPositionResponse(BaseModel):
    """Binance USD-M futures position."""

    symbol: str
    side: str
    position_amt: float
    entry_price: float
    mark_price: float
    notional_usdt: float
    unrealized_pnl: float
    leverage: float
    margin_type: str
    liquidation_price: float | None = None


class BinancePositionsResponse(BaseModel):
    """Combined Binance spot and USD-M futures positions response."""

    connection_id: str
    as_of: datetime
    account_scope: BinanceAccountScope
    totals: BinanceTotalsResponse
    spot_balances: list[SpotBalanceResponse]
    futures_positions: list[FuturesPositionResponse]
    warnings: list[str] = Field(default_factory=list)
