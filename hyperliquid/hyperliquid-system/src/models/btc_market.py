"""
BTC Market Data Models.

This module defines Pydantic models for all BTC market data collections.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.base import BaseDocument, TimestampMixin


# =============================================================================
# Orderbook Models
# =============================================================================


class OrderbookLevel(BaseModel):
    """Single price level in the orderbook."""

    px: float = Field(description="Price level")
    sz: float = Field(description="Total size at this level")
    n: int = Field(description="Number of orders at this level")


class BtcOrderbook(BaseDocument, TimestampMixin):
    """
    BTC Orderbook snapshot (time-series collection).

    Stores full depth orderbook snapshots with derived metrics.
    """

    t: datetime = Field(description="Snapshot timestamp")
    bids: List[OrderbookLevel] = Field(default_factory=list, description="Bid levels")
    asks: List[OrderbookLevel] = Field(default_factory=list, description="Ask levels")
    spread: float = Field(description="Spread (best_ask - best_bid)")
    mid_price: float = Field(alias="midPrice", description="Mid price")
    bid_depth: float = Field(alias="bidDepth", description="Total bid volume")
    ask_depth: float = Field(alias="askDepth", description="Total ask volume")
    imbalance: float = Field(description="Orderbook imbalance (-1 to 1)")


# =============================================================================
# Candle Models
# =============================================================================


class BtcCandle(BaseDocument, TimestampMixin):
    """
    BTC OHLCV Candle (time-series collection).

    Stores candlestick data for multiple intervals.
    """

    t: datetime = Field(description="Candle open timestamp")
    interval: str = Field(description="Candle interval (1m, 5m, 15m, 1h, 4h, 1d)")
    o: float = Field(description="Open price")
    h: float = Field(description="High price")
    l: float = Field(description="Low price")
    c: float = Field(description="Close price")
    v: float = Field(description="Volume in BTC")


# =============================================================================
# Trade Models
# =============================================================================


class BtcTrade(BaseDocument, TimestampMixin):
    """
    BTC Public Trade (time-series collection).

    Stores individual trades from the public feed.
    """

    tid: int = Field(description="Trade ID (unique)")
    t: datetime = Field(description="Trade timestamp")
    px: float = Field(description="Trade price")
    sz: float = Field(description="Trade size in BTC")
    side: str = Field(description="Trade side: A (Ask/Sell) or B (Bid/Buy)")
    hash: str = Field(description="Transaction hash")
    usd_value: float = Field(alias="usdValue", description="USD value of trade")


# =============================================================================
# Ticker Models
# =============================================================================


class BtcTicker(BaseDocument):
    """
    BTC 24h Ticker (single document, upserted).

    Stores current 24-hour statistics for BTC.
    """

    # Fixed ID for single document
    id: str = Field(default="btc_ticker", alias="_id")
    t: datetime = Field(description="Current timestamp")
    px: float = Field(description="Current mark price")
    last_sz: float = Field(alias="lastSz", description="Last trade size")
    volume_24h: float = Field(alias="volume24h", description="24h volume in USD")
    trades_24h: int = Field(alias="trades24h", description="Number of trades in 24h")
    high_24h: float = Field(alias="high24h", description="24h high price")
    low_24h: float = Field(alias="low24h", description="24h low price")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        alias="updatedAt",
        description="Last update timestamp",
    )


# =============================================================================
# Funding Models
# =============================================================================


class BtcFunding(BaseDocument, TimestampMixin):
    """
    BTC Funding Rate History (regular collection, upserted by timestamp).

    Stores historical funding rates for BTC.
    """

    t: datetime = Field(description="Funding timestamp")
    funding_rate: float = Field(alias="fundingRate", description="Funding rate")
    next_funding_time: Optional[datetime] = Field(
        default=None,
        alias="nextFundingTime",
        description="Next funding timestamp",
    )


# =============================================================================
# Open Interest Models
# =============================================================================


class BtcOpenInterest(BaseDocument, TimestampMixin):
    """
    BTC Open Interest (regular collection, upserted by date).

    Stores daily open interest data.
    """

    date: str = Field(description="Date (YYYY-MM-DD)")
    open_interest: float = Field(alias="openInterest", description="Open interest in USD")


# =============================================================================
# Liquidity Models
# =============================================================================


class BtcLiquidity(BaseDocument, TimestampMixin):
    """
    BTC Liquidity Metrics (regular collection, upserted by date).

    Stores daily liquidity and slippage data.
    """

    date: str = Field(description="Date (YYYY-MM-DD)")
    mid_price: float = Field(alias="midPrice", description="Mid price")
    median_liquidity: float = Field(alias="medianLiquidity", description="Median liquidity")
    slippage_1k: float = Field(alias="slippage1k", description="Slippage for $1,000 trade")
    slippage_3k: float = Field(alias="slippage3k", description="Slippage for $3,000 trade")
    slippage_10k: float = Field(alias="slippage10k", description="Slippage for $10,000 trade")
    slippage_30k: Optional[float] = Field(
        default=None, alias="slippage30k", description="Slippage for $30,000 trade"
    )
    slippage_100k: Optional[float] = Field(
        default=None, alias="slippage100k", description="Slippage for $100,000 trade"
    )


# =============================================================================
# Liquidation Models
# =============================================================================


class BtcLiquidation(BaseDocument, TimestampMixin):
    """
    BTC Liquidations (regular collection, upserted by date).

    Stores daily liquidation data.
    """

    date: str = Field(description="Date (YYYY-MM-DD)")
    notional_liquidated: float = Field(
        alias="notionalLiquidated", description="Total notional value liquidated (USD)"
    )
