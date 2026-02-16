"""
Signal Models.

This module defines Pydantic models for trading signals.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.models.base import BaseDocument, TimestampMixin


# =============================================================================
# BTC Signal Models
# =============================================================================


class BtcSignal(BaseDocument, TimestampMixin):
    """
    BTC Trading Signal (time-series collection).

    Stores individual signals generated from trader activity or market conditions.
    """

    t: datetime = Field(description="Signal timestamp")
    signal_type: str = Field(
        alias="signalType",
        description="Signal type: position_change, aggregated_bias, funding_signal",
    )
    eth_address: Optional[str] = Field(
        default=None, alias="ethAddress", description="Trader address (if individual signal)"
    )
    coin: str = Field(description="Coin the signal is for (usually BTC)")
    direction: str = Field(description="Direction: long, short, flat")
    size: float = Field(description="Position size (if applicable)")
    confidence: float = Field(description="Signal confidence (0-1)")
    price: float = Field(description="Price at signal time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional signal metadata")


# =============================================================================
# Aggregated Signal Models
# =============================================================================


class AggregatedBtcSignal(BaseDocument, TimestampMixin):
    """
    Aggregated BTC Signal (time-series collection).

    Stores aggregated signals combining all tracked trader positions.
    """

    t: datetime = Field(description="Signal timestamp")
    long_score: float = Field(alias="longScore", description="Weighted long score")
    short_score: float = Field(alias="shortScore", description="Weighted short score")
    total_weight: float = Field(alias="totalWeight", description="Total weight used")
    traders_long: int = Field(alias="tradersLong", description="Number of traders long")
    traders_short: int = Field(alias="tradersShort", description="Number of traders short")
    traders_flat: int = Field(alias="tradersFlat", description="Number of traders flat")
    net_exposure: float = Field(alias="netExposure", description="Net BTC exposure")
    long_bias: float = Field(alias="longBias", description="Long bias ratio (0-1)")
    short_bias: float = Field(alias="shortBias", description="Short bias ratio (0-1)")
    recommendation: str = Field(description="Recommendation: LONG, SHORT, NEUTRAL")
    confidence: float = Field(description="Signal confidence (0-1)")
    price: float = Field(description="BTC price at signal time")


# =============================================================================
# Signal Helper Functions
# =============================================================================


def determine_recommendation(long_bias: float, short_bias: float) -> str:
    """
    Determine trading recommendation from bias values.

    Args:
        long_bias: Long bias ratio (0-1)
        short_bias: Short bias ratio (0-1)

    Returns:
        Recommendation string: LONG, SHORT, or NEUTRAL
    """
    if long_bias > 0.6:
        return "LONG"
    elif short_bias > 0.6:
        return "SHORT"
    return "NEUTRAL"


def calculate_confidence(
    long_bias: float,
    short_bias: float,
    total_weight: float,
    traders_involved: int,
) -> float:
    """
    Calculate signal confidence based on multiple factors.

    Args:
        long_bias: Long bias ratio
        short_bias: Short bias ratio
        total_weight: Total weight of traders
        traders_involved: Number of traders contributing

    Returns:
        Confidence score (0-1)
    """
    # Bias strength (0-0.4 range, normalized)
    bias_strength = abs(long_bias - short_bias) / 0.4
    bias_strength = min(bias_strength, 1.0)

    # Weight factor (capped at 1.0)
    weight_factor = min(total_weight / 50, 1.0)  # Assuming max weight ~50

    # Trader count factor
    trader_factor = min(traders_involved / 100, 1.0)  # More traders = higher confidence

    # Combined confidence
    confidence = (bias_strength * 0.5) + (weight_factor * 0.3) + (trader_factor * 0.2)

    return round(confidence, 4)
