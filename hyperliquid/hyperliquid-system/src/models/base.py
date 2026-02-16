"""
Base models and utilities for the Hyperliquid BTC Trading System.

This module provides shared model utilities, base classes, and enums
used across all data models in the system.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class PyObjectId(str):
    """
    Custom type for MongoDB ObjectId handling with Pydantic.

    Converts between ObjectId and string representations.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.with_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v: Any, info) -> str:
        """Validate and convert to string representation."""
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")


class CollectionName(str, Enum):
    """Enumeration of all MongoDB collection names."""

    # BTC Market Data
    BTC_CANDLES = "btc_candles"
    BTC_ORDERBOOK = "btc_orderbook"
    BTC_TRADES = "btc_trades"
    BTC_TICKER = "btc_ticker"
    BTC_FUNDING = "btc_funding_history"
    BTC_OPEN_INTEREST = "btc_open_interest"
    BTC_LIQUIDITY = "btc_liquidity"
    BTC_LIQUIDATIONS = "btc_liquidations"
    ALL_MIDS = "all_mids"

    # Trader Data
    TRACKED_TRADERS = "tracked_traders"
    TRADER_POSITIONS = "trader_positions"
    TRADER_CURRENT_STATE = "trader_current_state"
    TRADER_ORDERS = "trader_orders"
    LEADERBOARD_HISTORY = "leaderboard_history"

    # Signals
    BTC_SIGNALS = "btc_signals"
    AGGREGATED_SIGNALS = "aggregated_btc_signals"


class TimestampMixin(BaseModel):
    """
    Mixin providing common timestamp fields for documents.

    Includes createdAt for document creation time.
    """

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        alias="createdAt",
        description="Document creation timestamp",
    )


class BaseDocument(BaseModel):
    """
    Base model for all MongoDB documents.

    Provides common configuration and fields.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        use_enum_values=True,
    )

    id: PyObjectId | None = Field(default=None, alias="_id")


# =============================================================================
# Index Definitions
# =============================================================================

# Time-series collection indexes (no unique indexes - MongoDB doesn't support them on time-series)
TIMESERIES_INDEXES = {
    CollectionName.BTC_CANDLES: [
        {"keys": [("t", 1), ("interval", 1)]},
        {"keys": [("interval", 1), ("t", -1)]},
    ],
    CollectionName.BTC_ORDERBOOK: [
        {"keys": [("t", -1)]},
    ],
    CollectionName.BTC_TRADES: [
        {"keys": [("tid", 1)]},
        {"keys": [("t", -1)]},
    ],
    CollectionName.TRADER_POSITIONS: [
        {"keys": [("ethAddress", 1), ("t", -1)]},
        {"keys": [("t", -1)]},
    ],
    CollectionName.TRADER_ORDERS: [
        {"keys": [("ethAddress", 1), ("oid", 1)]},  # For deduplication and lookup
        {"keys": [("oid", 1)]},
        {"keys": [("ethAddress", 1), ("timestamp", -1)]},
        {"keys": [("coin", 1), ("timestamp", -1)]},
    ],
    CollectionName.BTC_SIGNALS: [
        {"keys": [("t", -1)]},
        {"keys": [("signalType", 1), ("t", -1)]},
        {"keys": [("coin", 1), ("t", -1)]},
    ],
    CollectionName.ALL_MIDS: [
        {"keys": [("coin", 1), ("t", -1)]},
        {"keys": [("t", -1)]},
    ],
    CollectionName.LEADERBOARD_HISTORY: [
        {"keys": [("t", -1)]},
    ],
}

# Regular collection indexes
REGULAR_INDEXES = {
    CollectionName.BTC_FUNDING: [
        {"keys": [("t", 1)], "unique": True},
    ],
    CollectionName.BTC_OPEN_INTEREST: [
        {"keys": [("date", 1)], "unique": True},
    ],
    CollectionName.BTC_LIQUIDITY: [
        {"keys": [("date", 1)], "unique": True},
    ],
    CollectionName.BTC_LIQUIDATIONS: [
        {"keys": [("date", 1)], "unique": True},
    ],
    CollectionName.TRACKED_TRADERS: [
        {"keys": [("ethAddress", 1)], "unique": True},
        {"keys": [("score", -1)]},
        {"keys": [("isActive", 1)]},
    ],
    CollectionName.TRADER_CURRENT_STATE: [
        {"keys": [("ethAddress", 1)], "unique": True},
    ],
}
