# src/market_scraper/storage/models.py

"""Clean data models for MongoDB collections.

These models are optimized for:
- Minimal storage size (short field names)
- Time-series queries
- Efficient indexing
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============== Market Data Models ==============


class Trade(BaseModel):
    """Trade data model.

    Collection: {symbol}_trades (e.g., btc_trades)
    """

    tid: int = Field(..., description="Trade ID (unique)")
    t: datetime = Field(..., description="Timestamp (UTC)")
    p: float = Field(..., description="Price")
    sz: float = Field(..., description="Size")
    side: str = Field(..., description="Side: B (bid/buy) or A (ask/sell)")
    usd: float = Field(..., description="USD value (price * size)")


class OrderbookLevel(BaseModel):
    """Single orderbook level."""

    p: float = Field(..., description="Price")
    sz: float = Field(..., description="Size")


class Orderbook(BaseModel):
    """Orderbook snapshot model.

    Collection: {symbol}_orderbook (e.g., btc_orderbook)
    """

    t: datetime = Field(..., description="Timestamp (UTC)")
    bids: list[OrderbookLevel] = Field(default_factory=list, description="Top bids")
    asks: list[OrderbookLevel] = Field(default_factory=list, description="Top asks")
    mid: float = Field(..., description="Mid price")
    spr: float = Field(..., description="Spread (as decimal)")
    imb: float = Field(..., description="Imbalance (-1 to 1)")


class Candle(BaseModel):
    """OHLCV candle model.

    Collection: {symbol}_candles_{interval} (e.g., btc_candles_1m)
    """

    t: datetime = Field(..., description="Candle start timestamp")
    o: float = Field(..., description="Open price")
    h: float = Field(..., description="High price")
    l: float = Field(..., description="Low price")  # noqa: E741
    c: float = Field(..., description="Close price")
    v: float = Field(..., description="Volume")


class MarkPrice(BaseModel):
    """Mark price model.

    Collection: mark_prices
    """

    t: datetime = Field(..., description="Timestamp")
    symbol: str = Field(..., description="Symbol")
    price: float = Field(..., description="Mark price")


# ============== Trader Models ==============


class TraderPosition(BaseModel):
    """Trader position snapshot.

    Collection: trader_positions (time-series)
    """

    eth: str = Field(..., description="Trader Ethereum address")
    t: datetime = Field(..., description="Timestamp")
    coin: str = Field(..., description="Coin/symbol")
    sz: float = Field(..., description="Position size (positive=long, negative=short)")
    ep: float = Field(..., description="Entry price")
    mp: float = Field(default=0, description="Mark price")
    upnl: float = Field(default=0, description="Unrealized PnL")
    lev: float = Field(default=1, description="Leverage")
    liq: float | None = Field(default=None, description="Liquidation price")


class TraderScore(BaseModel):
    """Trader score snapshot.

    Collection: trader_scores (time-series)
    """

    eth: str = Field(..., description="Trader Ethereum address")
    t: datetime = Field(..., description="Timestamp")
    score: float = Field(..., description="Composite score (0-100+)")
    tags: list[str] = Field(default_factory=list, description="Trader tags")
    acct_val: float = Field(default=0, description="Account value")
    all_roi: float = Field(default=0, description="All-time ROI")
    month_roi: float = Field(default=0, description="Month ROI")
    week_roi: float = Field(default=0, description="Week ROI")


class TrackedTrader(BaseModel):
    """Currently tracked trader.

    Collection: tracked_traders (regular collection, upserted)
    """

    eth: str = Field(..., description="Trader Ethereum address")
    name: str | None = Field(default=None, description="Display name")
    score: float = Field(default=0, description="Current score")
    tags: list[str] = Field(default_factory=list, description="Tags")
    active: bool = Field(default=True, description="Is being tracked")
    added_at: datetime = Field(default_factory=datetime.utcnow, description="When added")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update")


# ============== Signal Models ==============


class TradingSignal(BaseModel):
    """Trading signal model.

    Collection: signals (time-series)
    """

    t: datetime = Field(..., description="Signal timestamp")
    symbol: str = Field(..., description="Symbol")
    rec: str = Field(..., description="Recommendation: BUY, SELL, NEUTRAL")
    conf: float = Field(..., description="Confidence (0-1)")
    long_bias: float = Field(..., description="Long bias (0-1)")
    short_bias: float = Field(..., description="Short bias (0-1)")
    net_exp: float = Field(..., description="Net exposure")
    t_long: int = Field(default=0, description="Traders long")
    t_short: int = Field(default=0, description="Traders short")
    t_flat: int = Field(default=0, description="Traders flat")
    price: float = Field(default=0, description="Price at signal time")


class TraderSignal(BaseModel):
    """Individual trader signal.

    Collection: trader_signals (time-series)
    """

    eth: str = Field(..., description="Trader address")
    t: datetime = Field(..., description="Signal timestamp")
    symbol: str = Field(..., description="Symbol")
    action: str = Field(..., description="Action: open, close, increase, decrease")
    dir: str = Field(..., description="Direction: long, short")
    sz: float = Field(..., description="Position size")
    conf: float = Field(..., description="Confidence")
    score: float = Field(default=0, description="Trader score")


# ============== Leaderboard Models ==============


class LeaderboardSnapshot(BaseModel):
    """Leaderboard snapshot.

    Collection: leaderboard_history (time-series)
    """

    t: datetime = Field(..., description="Snapshot timestamp")
    traders: list[dict[str, Any]] = Field(default_factory=list, description="Trader data")
    count: int = Field(default=0, description="Number of traders")


# ============== Collection Names ==============


class CollectionName:
    """MongoDB collection names."""

    # Market data (symbol-specific)
    TRADES = "{symbol}_trades"
    ORDERBOOK = "{symbol}_orderbook"
    CANDLES = "{symbol}_candles_{interval}"
    MARK_PRICES = "mark_prices"

    # Trader data
    TRADER_POSITIONS = "trader_positions"
    TRADER_SCORES = "trader_scores"
    TRACKED_TRADERS = "tracked_traders"
    TRADER_CURRENT_STATE = "trader_current_state"

    # Signals
    SIGNALS = "signals"
    TRADER_SIGNALS = "trader_signals"

    # Leaderboard
    LEADERBOARD = "leaderboard_history"
    LEADERBOARD_HISTORY = "leaderboard_history"  # Alias for clarity

    @classmethod
    def trades(cls, symbol: str) -> str:
        """Get trades collection name for symbol."""
        return cls.TRADES.format(symbol=symbol.lower())

    @classmethod
    def orderbook(cls, symbol: str) -> str:
        """Get orderbook collection name for symbol."""
        return cls.ORDERBOOK.format(symbol=symbol.lower())

    @classmethod
    def candles(cls, symbol: str, interval: str) -> str:
        """Get candles collection name for symbol and interval."""
        return cls.CANDLES.format(symbol=symbol.lower(), interval=interval)
