"""
Leaderboard Collection Job.

This module fetches and stores the Hyperliquid leaderboard.
"""

from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.strategies.trader_scoring import calculate_trader_score, select_top_traders
from src.utils.helpers import utcnow


async def fetch_leaderboard(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Fetch and process the leaderboard without storing the full raw data.

    Args:
        client: Stats Data API client
        db: MongoDB database

    Returns:
        Dictionary with fetch results
    """
    try:
        # Fetch leaderboard from API
        leaderboard_data = await client.get_leaderboard()

        if not leaderboard_data:
            logger.warning("No leaderboard data received")
            return {"success": False, "error": "No data"}

        rows = leaderboard_data.get("leaderboardRows", [])
        trader_count = len(rows)

        # Store a lightweight snapshot with just counts and timestamp
        # Don't store the full traders array (too large for MongoDB)
        snapshot = {
            "t": utcnow(),
            "traderCount": trader_count,
            "createdAt": utcnow(),
        }

        await db[CollectionName.LEADERBOARD_HISTORY].insert_one(snapshot)

        logger.info(f"Processed leaderboard with {trader_count} traders")

        # Update tracked traders directly from this data
        await _update_tracked_from_leaderboard(db, rows)

        return {
            "success": True,
            "traderCount": trader_count,
        }

    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        return {"success": False, "error": str(e)}


async def _update_tracked_from_leaderboard(
    db: AsyncIOMotorDatabase,
    rows: List[Dict],
) -> None:
    """Update tracked traders with position inference filtering."""
    from src.strategies.trader_scoring import calculate_trader_score
    from src.utils.position_inference import filter_traders_with_positions

    tracked_collection = db[CollectionName.TRACKED_TRADERS]

    # Step 1: Score all traders
    logger.info("Scoring traders...")
    scored_traders = []
    for trader in rows:
        score = calculate_trader_score(trader)
        if score >= settings.trader_min_score:
            scored_traders.append(
                {
                    "ethAddress": trader.get("ethAddress", ""),
                    "displayName": trader.get("displayName"),
                    "accountValue": float(trader.get("accountValue", 0)),
                    "score": score,
                    "windowPerformances": trader.get("windowPerformances", []),
                }
            )

    # Step 2: Sort by score
    scored_traders.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Scored {len(scored_traders)} traders (min_score: {settings.trader_min_score})")

    # Step 3: Filter for likely active positions
    selected = filter_traders_with_positions(
        scored_traders, target_count=settings.max_tracked_traders
    )

    # Step 4: If not enough, take best remaining (fallback)
    if len(selected) < settings.max_tracked_traders:
        remaining = [t for t in scored_traders if t not in selected]
        needed = settings.max_tracked_traders - len(selected)
        selected.extend(remaining[:needed])
        logger.warning(f"Added {needed} traders without position filter (fallback)")

    # Step 5: Store in database
    selected_addresses = {t["ethAddress"] for t in selected}
    now = utcnow()

    new_count = 0
    updated_count = 0

    for trader in selected:
        address = trader["ethAddress"]
        performances = _parse_performances(trader.get("windowPerformances", []))
        position_inference = trader.get("position_inference", {})

        doc = {
            "ethAddress": address,
            "displayName": trader.get("displayName"),
            "score": trader["score"],
            "accountValue": trader["accountValue"],
            "performances": performances,
            "isActive": True,
            "hasLikelyPosition": position_inference.get("has_position", True),
            "positionInferenceReason": position_inference.get("reason", "no_filter"),
            "tags": _generate_tags(trader),
            "lastUpdated": now,
        }

        result = await tracked_collection.update_one(
            {"ethAddress": address},
            {"$set": doc, "$setOnInsert": {"addedAt": now}},
            upsert=True,
        )
        if result.upserted_id:
            new_count += 1
        else:
            updated_count += 1

    # Deactivate traders not in selection
    if selected_addresses:
        deactivate_result = await tracked_collection.update_many(
            {"ethAddress": {"$nin": list(selected_addresses)}, "isActive": True},
            {"$set": {"isActive": False, "lastUpdated": now}},
        )
        deactivated_count = deactivate_result.modified_count
    else:
        deactivated_count = 0

    logger.info(
        f"Updated tracked traders: {new_count} new, {updated_count} updated, "
        f"{deactivated_count} deactivated, {len(selected)} total active"
    )


async def update_tracked_traders(
    db: AsyncIOMotorDatabase,
    stats_client,
) -> Dict:
    """
    Update tracked traders based on leaderboard.

    Args:
        db: MongoDB database
        stats_client: Stats Data API client

    Returns:
        Dictionary with update results
    """
    tracked_collection = db[CollectionName.TRACKED_TRADERS]
    leaderboard_collection = db[CollectionName.LEADERBOARD_HISTORY]

    try:
        # Get latest leaderboard snapshot
        latest_snapshot = await leaderboard_collection.find_one(sort=[("t", -1)])

        if not latest_snapshot:
            logger.warning("No leaderboard snapshot found")
            return {"success": False, "error": "No snapshot"}

        leaderboard_data = {"leaderboardRows": latest_snapshot.get("traders", [])}

        # Select top traders
        selected = select_top_traders(
            leaderboard_data,
            max_count=settings.max_tracked_traders,
            min_score=settings.trader_min_score,
        )

        # Get selected addresses for atomic operations
        selected_addresses = {t["ethAddress"] for t in selected}
        now = utcnow()

        # Prepare updates
        new_count = 0
        updated_count = 0

        for trader in selected:
            address = trader["ethAddress"]

            # Parse performances
            performances = _parse_performances(trader.get("windowPerformances", []))

            doc = {
                "ethAddress": address,
                "displayName": trader.get("displayName"),
                "score": trader["score"],
                "accountValue": trader["accountValue"],
                "performances": performances,
                "isActive": True,
                "tags": _generate_tags(trader),
                "lastUpdated": now,
            }

            # Use upsert for atomic insert/update
            result = await tracked_collection.update_one(
                {"ethAddress": address},
                {"$set": doc, "$setOnInsert": {"addedAt": now}},
                upsert=True,
            )
            if result.upserted_id:
                new_count += 1
            else:
                updated_count += 1

        # Deactivate traders not in selection (atomic operation)
        if selected_addresses:
            deactivate_result = await tracked_collection.update_many(
                {"ethAddress": {"$nin": list(selected_addresses)}, "isActive": True},
                {"$set": {"isActive": False, "lastUpdated": now}},
            )
            deactivated_count = deactivate_result.modified_count
        else:
            deactivated_count = 0

        logger.info(
            f"Updated tracked traders: {new_count} new, {updated_count} updated, {deactivated_count} deactivated"
        )

        return {
            "success": True,
            "newTraders": new_count,
            "updatedTraders": updated_count,
            "totalActive": len(selected),
        }

    except Exception as e:
        logger.error(f"Error updating tracked traders: {e}")
        return {"success": False, "error": str(e)}


def _parse_performances(performances: List) -> Dict:
    """Parse window performances from list format."""
    parsed = {}
    for window_data in performances:
        if len(window_data) >= 2:
            window = window_data[0]
            metrics = window_data[1]
            parsed[window] = {
                "pnl": float(metrics.get("pnl", 0)),
                "roi": float(metrics.get("roi", 0)),
                "vlm": float(metrics.get("vlm", 0)),
            }
    return parsed


def _generate_tags(trader: Dict) -> List[str]:
    """Generate tags for a trader based on their metrics."""
    tags = []

    account_value = trader.get("accountValue", 0)
    score = trader.get("score", 0)
    performances = _parse_performances(trader.get("windowPerformances", []))

    # Size tags
    if account_value >= 10_000_000:
        tags.append("whale")
    elif account_value >= 1_000_000:
        tags.append("large")

    # Performance tags
    if score >= 80:
        tags.append("top_performer")
    elif score >= 60:
        tags.append("good_performer")

    # Consistency tags
    day_roi = performances.get("day", {}).get("roi", 0)
    week_roi = performances.get("week", {}).get("roi", 0)
    month_roi = performances.get("month", {}).get("roi", 0)

    if all([day_roi > 0, week_roi > 0, month_roi > 0]):
        tags.append("consistent")

    # Volume tags
    month_volume = performances.get("month", {}).get("vlm", 0)
    if month_volume >= 100_000_000:
        tags.append("high_volume")
    elif month_volume >= 10_000_000:
        tags.append("medium_volume")

    return tags


async def get_tracked_trader_addresses(
    db: AsyncIOMotorDatabase,
    active_only: bool = True,
) -> List[str]:
    """
    Get list of tracked trader addresses.

    Args:
        db: MongoDB database
        active_only: Only return active traders

    Returns:
        List of Ethereum addresses
    """
    collection = db[CollectionName.TRACKED_TRADERS]

    query = {}
    if active_only:
        query["isActive"] = True

    cursor = collection.find(query, {"ethAddress": 1}).sort("score", -1)
    docs = await cursor.to_list(length=None)

    return [doc["ethAddress"] for doc in docs]


async def get_tracked_traders(
    db: AsyncIOMotorDatabase,
    limit: int = 100,
    active_only: bool = True,
) -> List[Dict]:
    """
    Get tracked traders with their data.

    Args:
        db: MongoDB database
        limit: Maximum number of traders
        active_only: Only return active traders

    Returns:
        List of trader documents
    """
    collection = db[CollectionName.TRACKED_TRADERS]

    query = {}
    if active_only:
        query["isActive"] = True

    cursor = collection.find(query).sort("score", -1).limit(limit)
    return await cursor.to_list(length=limit)
