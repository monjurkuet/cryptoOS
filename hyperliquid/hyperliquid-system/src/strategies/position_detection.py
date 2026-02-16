"""
Position Detection Module.

This module provides functions for detecting and analyzing position changes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def detect_position_changes(
    prev_state: Optional[Dict[str, Any]],
    curr_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Detect position changes between two state snapshots.

    Args:
        prev_state: Previous clearinghouse state (can be None for first snapshot)
        curr_state: Current clearinghouse state

    Returns:
        List of position change dictionaries
    """
    changes = []

    # Get positions from both states
    prev_positions = _extract_positions(prev_state)
    curr_positions = _extract_positions(curr_state)

    # Get all coins from both states
    all_coins = set(prev_positions.keys()) | set(curr_positions.keys())

    for coin in all_coins:
        prev_pos = prev_positions.get(coin)
        curr_pos = curr_positions.get(coin)

        prev_size = float(prev_pos.get("szi", 0)) if prev_pos else 0
        curr_size = float(curr_pos.get("szi", 0)) if curr_pos else 0

        if prev_size != curr_size:
            change = {
                "coin": coin,
                "prevSize": prev_size,
                "currSize": curr_size,
                "delta": curr_size - prev_size,
                "direction": _get_direction(curr_size),
                "action": _get_action(prev_size, curr_size),
                "timestamp": datetime.utcnow(),
            }

            # Add position details if not closed
            if curr_pos:
                change["entryPx"] = float(curr_pos.get("entryPx", 0))
                change["positionValue"] = float(curr_pos.get("positionValue", 0))
                change["unrealizedPnl"] = float(curr_pos.get("unrealizedPnl", 0))
                change["leverage"] = _get_leverage(curr_pos)

            changes.append(change)

    return changes


def _extract_positions(state: Optional[Dict[str, Any]]) -> Dict[str, Dict]:
    """
    Extract positions from a clearinghouse state.

    Args:
        state: Clearinghouse state dictionary

    Returns:
        Dictionary mapping coin to position details
    """
    positions = {}

    if not state:
        return positions

    asset_positions = state.get("assetPositions", [])

    for pos in asset_positions:
        position = pos.get("position", {})
        coin = position.get("coin")
        if coin:
            positions[coin] = position

    return positions


def _get_direction(size: float) -> str:
    """Get position direction from size."""
    if size > 0:
        return "long"
    elif size < 0:
        return "short"
    return "flat"


def _get_action(prev_size: float, curr_size: float) -> str:
    """Get action type from position size changes."""
    if prev_size == 0 and curr_size != 0:
        return "open"
    elif prev_size != 0 and curr_size == 0:
        return "close"
    elif prev_size != 0 and curr_size != 0:
        # Check if increased or decreased
        if abs(curr_size) > abs(prev_size):
            return "increase"
        elif abs(curr_size) < abs(prev_size):
            return "decrease"
        else:
            return "modify"  # Same size, might be entry price change
    return "unknown"


def _get_leverage(position: Dict) -> float:
    """Extract leverage from position."""
    leverage = position.get("leverage", {})
    if isinstance(leverage, dict):
        return float(leverage.get("value", 0))
    return float(leverage) if leverage else 0


def get_position_for_coin(state: Dict[str, Any], coin: str) -> Optional[Dict]:
    """
    Get position for a specific coin from clearinghouse state.

    Args:
        state: Clearinghouse state dictionary
        coin: Coin ticker to find

    Returns:
        Position dictionary or None
    """
    positions = _extract_positions(state)
    return positions.get(coin)


def calculate_btc_exposure(positions: List[Dict[str, Any]]) -> float:
    """
    Calculate net BTC exposure from a list of positions.

    This considers:
    - Direct BTC position
    - Correlated assets (ETH, SOL with correlation weights)

    Args:
        positions: List of position dictionaries

    Returns:
        Net BTC exposure (positive = long, negative = short)
    """
    # Correlation weights for BTC-correlated assets
    correlation_weights = {
        "BTC": 1.0,
        "ETH": 0.7,  # ETH typically correlates with BTC
        "SOL": 0.6,
    }

    total_exposure = 0.0

    for pos in positions:
        coin = pos.get("coin", "")
        szi = float(pos.get("szi", 0))
        position_value = float(pos.get("positionValue", 0))

        if coin in correlation_weights:
            # Convert position value to BTC-equivalent
            weight = correlation_weights[coin]
            # Use position value directly (direction encoded in szi)
            exposure = position_value if szi != 0 else 0
            total_exposure += exposure * weight

    return total_exposure


def calculate_account_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate summary metrics from clearinghouse state.

    Args:
        state: Clearinghouse state dictionary

    Returns:
        Dictionary with account summary metrics
    """
    margin_summary = state.get("marginSummary", {})
    positions = _extract_positions(state)

    # Calculate position counts
    long_count = sum(1 for p in positions.values() if float(p.get("szi", 0)) > 0)
    short_count = sum(1 for p in positions.values() if float(p.get("szi", 0)) < 0)

    # Calculate total unrealized PnL
    total_unrealized_pnl = sum(float(p.get("unrealizedPnl", 0)) for p in positions.values())

    return {
        "accountValue": float(margin_summary.get("accountValue", 0)),
        "totalNotionalPos": float(margin_summary.get("totalNtlPos", 0)),
        "totalMarginUsed": float(margin_summary.get("totalMarginUsed", 0)),
        "withdrawable": float(state.get("withdrawable", 0)),
        "positionCount": len(positions),
        "longCount": long_count,
        "shortCount": short_count,
        "totalUnrealizedPnl": total_unrealized_pnl,
        "btcExposure": calculate_btc_exposure(list(positions.values())),
    }


def filter_btc_relevant_changes(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter position changes relevant to BTC trading.

    Args:
        changes: List of position changes

    Returns:
        List of BTC-relevant changes
    """
    btc_correlated = {"BTC", "ETH", "SOL"}
    return [c for c in changes if c.get("coin") in btc_correlated]


def aggregate_position_changes(
    changes: List[Dict[str, Any]],
    by: str = "coin",
) -> Dict[str, Dict]:
    """
    Aggregate position changes by a field.

    Args:
        changes: List of position changes
        by: Field to aggregate by ("coin", "direction", "action")

    Returns:
        Dictionary mapping field value to aggregated metrics
    """
    aggregated = {}

    for change in changes:
        key = change.get(by, "unknown")

        if key not in aggregated:
            aggregated[key] = {
                "count": 0,
                "totalDelta": 0,
                "opens": 0,
                "closes": 0,
                "increases": 0,
                "decreases": 0,
            }

        aggregated[key]["count"] += 1
        aggregated[key]["totalDelta"] += change.get("delta", 0)

        action = change.get("action", "")
        if action == "open":
            aggregated[key]["opens"] += 1
        elif action == "close":
            aggregated[key]["closes"] += 1
        elif action == "increase":
            aggregated[key]["increases"] += 1
        elif action == "decrease":
            aggregated[key]["decreases"] += 1

    return aggregated
