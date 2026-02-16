"""
Trader Scoring Module.

This module provides functions for scoring and selecting traders from the leaderboard.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from src.config import settings


def calculate_trader_score(trader: Dict[str, Any]) -> float:
    """
    Calculate a score for a trader based on their performance metrics.

    Scoring weights:
    - All-time ROI: 30%
    - Month ROI: 25%
    - Week ROI: 20%
    - Account value: 15%
    - Volume: 10%

    Args:
        trader: Trader data dictionary from leaderboard

    Returns:
        Calculated score (0-100)
    """
    score = 0.0

    # Get performances
    performances = trader.get("windowPerformances", {})
    if isinstance(performances, list):
        # Convert list format to dict
        perfs = {}
        for window_data in performances:
            if len(window_data) >= 2:
                window = window_data[0]
                metrics = window_data[1]
                perfs[window] = metrics
        performances = perfs

    # All-time ROI (30% weight, max 30 points)
    all_time_roi = 0.0
    if "allTime" in performances:
        all_time_roi = float(performances["allTime"].get("roi", 0))
    score += min(all_time_roi * 30, 30)

    # Month ROI (25% weight, max 25 points)
    month_roi = 0.0
    if "month" in performances:
        month_roi = float(performances["month"].get("roi", 0))
    score += min(month_roi * 50, 25)

    # Week ROI (20% weight, max 20 points, can be negative)
    week_roi = 0.0
    if "week" in performances:
        week_roi = float(performances["week"].get("roi", 0))
    score += max(min(week_roi * 100, 20), -10)

    # Account value (15% weight, max 15 points)
    account_value = float(trader.get("accountValue", 0))
    if account_value >= 10_000_000:
        score += 15
    elif account_value >= 5_000_000:
        score += 12
    elif account_value >= 1_000_000:
        score += 8
    elif account_value >= 100_000:
        score += 4

    # Volume (10% weight, max 10 points)
    month_volume = 0.0
    if "month" in performances:
        month_volume = float(performances["month"].get("vlm", 0))
    if month_volume >= 100_000_000:
        score += 10
    elif month_volume >= 50_000_000:
        score += 7
    elif month_volume >= 10_000_000:
        score += 4
    elif month_volume >= 1_000_000:
        score += 2

    # Bonus: Positive consistency (all timeframes positive)
    day_roi = float(performances.get("day", {}).get("roi", 0) or 0)
    week_roi_val = float(performances.get("week", {}).get("roi", 0) or 0)
    month_roi_val = float(performances.get("month", {}).get("roi", 0) or 0)

    if day_roi > 0 and week_roi_val > 0 and month_roi_val > 0:
        score += 5

    return round(score, 2)


def filter_btc_active_traders(
    traders: List[Dict[str, Any]],
    positions_map: Dict[str, Dict],
) -> List[str]:
    """
    Filter traders who are active in BTC.

    Args:
        traders: List of trader data
        positions_map: Map of ethAddress to their current positions

    Returns:
        List of ethAddresses of BTC-active traders
    """
    btc_active = []

    for trader in traders:
        address = trader.get("ethAddress", "")
        if not address:
            continue

        # Check if trader has BTC position
        positions = positions_map.get(address, {})
        asset_positions = positions.get("assetPositions", [])

        for pos in asset_positions:
            position = pos.get("position", {})
            if position.get("coin") == "BTC" and float(position.get("szi", 0)) != 0:
                btc_active.append(address)
                break

    return btc_active


async def filter_btc_active_traders_async(
    traders: List[Dict[str, Any]],
    api_client,
    concurrency: int = 10,
) -> List[str]:
    """
    Filter traders who are active in BTC using async API calls.

    Args:
        traders: List of trader data
        api_client: Hyperliquid API client
        concurrency: Maximum concurrent API calls

    Returns:
        List of ethAddresses of BTC-active traders
    """
    import asyncio

    btc_active = []
    semaphore = asyncio.Semaphore(concurrency)

    async def check_trader(trader: Dict[str, Any]) -> Optional[str]:
        address = trader.get("ethAddress", "")
        if not address:
            return None

        async with semaphore:
            try:
                state = await api_client.get_clearinghouse_state(address)
                asset_positions = state.get("assetPositions", [])

                for pos in asset_positions:
                    position = pos.get("position", {})
                    if position.get("coin") == "BTC" and float(position.get("szi", 0)) != 0:
                        return address
            except Exception as e:
                logger.warning(f"Error checking trader {address}: {e}")

        return None

    results = await asyncio.gather(*[check_trader(t) for t in traders])
    btc_active = [r for r in results if r is not None]

    logger.info(f"Found {len(btc_active)} BTC-active traders out of {len(traders)}")
    return btc_active


def select_top_traders(
    leaderboard_data: Dict[str, Any],
    max_count: int = 500,
    min_score: float = 50.0,
) -> List[Dict[str, Any]]:
    """
    Select top traders from leaderboard data based on score.

    Args:
        leaderboard_data: Raw leaderboard response
        max_count: Maximum number of traders to select
        min_score: Minimum score threshold

    Returns:
        List of selected trader dictionaries with scores
    """
    rows = leaderboard_data.get("leaderboardRows", [])

    # Calculate scores for all traders
    scored_traders = []
    for trader in rows:
        score = calculate_trader_score(trader)
        if score >= min_score:
            trader_info = {
                "ethAddress": trader.get("ethAddress", ""),
                "displayName": trader.get("displayName"),
                "accountValue": float(trader.get("accountValue", 0)),
                "score": score,
                "windowPerformances": trader.get("windowPerformances", []),
            }
            scored_traders.append(trader_info)

    # Sort by score
    scored_traders.sort(key=lambda x: x["score"], reverse=True)

    # Limit to max_count
    selected = scored_traders[:max_count]

    logger.info(f"Selected {len(selected)} traders (score >= {min_score})")
    return selected


def update_trader_scores(
    tracked_traders: List[Dict[str, Any]],
    leaderboard_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Update scores for tracked traders from new leaderboard data.

    Args:
        tracked_traders: List of currently tracked traders
        leaderboard_data: New leaderboard data

    Returns:
        List of updated trader dictionaries
    """
    # Create lookup from leaderboard
    leaderboard_lookup = {}
    for trader in leaderboard_data.get("leaderboardRows", []):
        address = trader.get("ethAddress", "")
        if address:
            leaderboard_lookup[address] = trader

    updated = []
    for trader in tracked_traders:
        address = trader.get("ethAddress", "")
        if address in leaderboard_lookup:
            # Update from leaderboard
            lb_trader = leaderboard_lookup[address]
            new_score = calculate_trader_score(lb_trader)

            trader["score"] = new_score
            trader["accountValue"] = float(lb_trader.get("accountValue", 0))
            trader["windowPerformances"] = lb_trader.get("windowPerformances", [])
            trader["displayName"] = lb_trader.get("displayName")
            trader["lastUpdated"] = datetime.utcnow()

        updated.append(trader)

    return updated


def get_trader_statistics(traders: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate aggregate statistics for a list of traders.

    Args:
        traders: List of trader dictionaries

    Returns:
        Dictionary with aggregate statistics
    """
    if not traders:
        return {
            "count": 0,
            "totalAccountValue": 0,
            "avgScore": 0,
            "avgRoi": 0,
        }

    total_value = sum(t.get("accountValue", 0) for t in traders)
    total_score = sum(t.get("score", 0) for t in traders)

    # Calculate average ROI
    rois = []
    for t in traders:
        perfs = t.get("windowPerformances", [])
        if isinstance(perfs, list):
            for p in perfs:
                if len(p) >= 2 and p[0] == "allTime":
                    rois.append(float(p[1].get("roi", 0)))
                    break

    avg_roi = sum(rois) / len(rois) if rois else 0

    return {
        "count": len(traders),
        "totalAccountValue": total_value,
        "avgAccountValue": total_value / len(traders),
        "avgScore": total_score / len(traders),
        "avgRoi": avg_roi,
    }
