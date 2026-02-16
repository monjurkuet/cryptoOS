"""
Signal Generation Module.

This module provides functions for generating trading signals from trader data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from src.models.signals import (
    AggregatedBtcSignal,
    BtcSignal,
    calculate_confidence,
    determine_recommendation,
)


def generate_individual_signal(
    eth_address: str,
    position_change: Dict[str, Any],
    trader_score: float,
    current_price: float,
) -> Optional[Dict[str, Any]]:
    """
    Generate a signal from an individual trader's position change.

    Args:
        eth_address: Trader's Ethereum address
        position_change: Position change dictionary
        trader_score: Trader's score (used for confidence)
        current_price: Current BTC price

    Returns:
        Signal dictionary or None if not relevant
    """
    coin = position_change.get("coin")
    if coin != "BTC":
        return None

    action = position_change.get("action", "")
    if action not in ["open", "close", "increase", "decrease"]:
        return None

    direction = position_change.get("direction", "")
    curr_size = position_change.get("currSize", 0)
    delta = position_change.get("delta", 0)

    # Calculate confidence based on trader score and position size
    score_confidence = min(trader_score / 100, 1.0)  # Normalize to 0-1
    size_confidence = min(abs(delta) / 10, 1.0)  # Assume 10 BTC is max confidence
    confidence = (score_confidence * 0.7) + (size_confidence * 0.3)

    signal = {
        "t": datetime.utcnow(),
        "signalType": "position_change",
        "ethAddress": eth_address,
        "coin": "BTC",
        "direction": direction,
        "size": abs(curr_size),
        "confidence": round(confidence, 4),
        "price": current_price,
        "metadata": {
            "action": action,
            "delta": delta,
            "traderScore": trader_score,
        },
    }

    return signal


async def generate_aggregated_signal(
    trader_states: Dict[str, Dict[str, Any]],
    trader_scores: Dict[str, float],
    current_price: float,
) -> Dict[str, Any]:
    """
    Generate an aggregated signal from all tracked trader positions.

    Args:
        trader_states: Map of ethAddress to their current state
        trader_scores: Map of ethAddress to their score
        current_price: Current BTC price

    Returns:
        Aggregated signal dictionary
    """
    long_score = 0.0
    short_score = 0.0
    total_weight = 0.0
    traders_long = 0
    traders_short = 0
    traders_flat = 0
    net_exposure = 0.0

    for eth_address, state in trader_states.items():
        score = trader_scores.get(eth_address, 50)  # Default score
        weight = score / 100  # Normalize to 0-1

        # Get BTC position
        positions = state.get("assetPositions", [])
        btc_position = None
        for pos in positions:
            if pos.get("position", {}).get("coin") == "BTC":
                btc_position = pos.get("position", {})
                break

        if btc_position:
            szi = float(btc_position.get("szi", 0))
            position_value = float(btc_position.get("positionValue", 0))

            # Weighted exposure
            exposure = szi * weight
            net_exposure += exposure

            if szi > 0:
                long_score += weight
                traders_long += 1
            elif szi < 0:
                short_score += weight
                traders_short += 1
            else:
                traders_flat += 1
        else:
            traders_flat += 1

        total_weight += weight

    # Calculate biases
    if total_weight > 0:
        long_bias = long_score / total_weight
        short_bias = short_score / total_weight
    else:
        long_bias = 0.0
        short_bias = 0.0

    # Determine recommendation
    recommendation = determine_recommendation(long_bias, short_bias)

    # Calculate confidence
    confidence = calculate_confidence(
        long_bias=long_bias,
        short_bias=short_bias,
        total_weight=total_weight,
        traders_involved=traders_long + traders_short,
    )

    signal = {
        "t": datetime.utcnow(),
        "longScore": round(long_score, 4),
        "shortScore": round(short_score, 4),
        "totalWeight": round(total_weight, 4),
        "tradersLong": traders_long,
        "tradersShort": traders_short,
        "tradersFlat": traders_flat,
        "netExposure": round(net_exposure, 4),
        "longBias": round(long_bias, 4),
        "shortBias": round(short_bias, 4),
        "recommendation": recommendation,
        "confidence": round(confidence, 4),
        "price": current_price,
    }

    logger.info(
        f"Aggregated signal: {recommendation} (long={long_bias:.2%}, "
        f"short={short_bias:.2%}, confidence={confidence:.2%})"
    )

    return signal


def calculate_signal_metrics(
    signals: List[Dict[str, Any]],
    timeframe: str = "day",
) -> Dict[str, Any]:
    """
    Calculate aggregate metrics from a list of signals.

    Args:
        signals: List of signal dictionaries
        timeframe: Timeframe for aggregation

    Returns:
        Dictionary with aggregate metrics
    """
    if not signals:
        return {
            "count": 0,
            "avgConfidence": 0,
            "longSignals": 0,
            "shortSignals": 0,
            "neutralSignals": 0,
        }

    long_count = sum(1 for s in signals if s.get("direction") == "long")
    short_count = sum(1 for s in signals if s.get("direction") == "short")
    neutral_count = sum(1 for s in signals if s.get("direction") == "flat")

    total_confidence = sum(s.get("confidence", 0) for s in signals)

    return {
        "count": len(signals),
        "avgConfidence": total_confidence / len(signals),
        "longSignals": long_count,
        "shortSignals": short_count,
        "neutralSignals": neutral_count,
        "longRatio": long_count / len(signals) if signals else 0,
        "shortRatio": short_count / len(signals) if signals else 0,
    }


def should_generate_alert(
    signal: Dict[str, Any],
    prev_signal: Optional[Dict[str, Any]] = None,
    threshold: float = 0.1,
) -> bool:
    """
    Determine if a signal should trigger an alert.

    Args:
        signal: Current signal
        prev_signal: Previous signal (for comparison)
        threshold: Minimum change threshold

    Returns:
        True if alert should be generated
    """
    confidence = signal.get("confidence", 0)
    recommendation = signal.get("recommendation", "")

    # High confidence signal
    if confidence >= 0.7:
        return True

    # Significant bias shift
    if prev_signal:
        prev_rec = prev_signal.get("recommendation", "")
        if recommendation != prev_rec:
            return True

        prev_long_bias = prev_signal.get("longBias", 0)
        curr_long_bias = signal.get("longBias", 0)
        if abs(curr_long_bias - prev_long_bias) >= threshold:
            return True

    return False


def get_trader_activity_summary(
    eth_address: str,
    recent_signals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Get a summary of recent activity for a trader.

    Args:
        eth_address: Trader's Ethereum address
        recent_signals: Recent signals from this trader

    Returns:
        Activity summary dictionary
    """
    btc_signals = [s for s in recent_signals if s.get("coin") == "BTC"]

    opens = sum(1 for s in btc_signals if s.get("metadata", {}).get("action") == "open")
    closes = sum(1 for s in btc_signals if s.get("metadata", {}).get("action") == "close")

    total_delta = sum(s.get("metadata", {}).get("delta", 0) for s in btc_signals)

    return {
        "ethAddress": eth_address,
        "signalCount": len(btc_signals),
        "opens": opens,
        "closes": closes,
        "totalDelta": total_delta,
        "lastActivity": btc_signals[0].get("t") if btc_signals else None,
    }
