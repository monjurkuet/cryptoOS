"""
BTC Orderbook Collection Job.

This module collects orderbook snapshots for BTC.
"""

from datetime import datetime
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


async def collect_orderbook(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC orderbook snapshot.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    collection = db[CollectionName.BTC_ORDERBOOK]

    try:
        # Fetch orderbook from API
        orderbook_data = await client.get_l2_book(settings.target_coin)

        if not orderbook_data:
            logger.warning("No orderbook data received")
            return {"success": False, "error": "No data"}

        # Parse levels
        levels = orderbook_data.get("levels", [])
        asks = levels[0] if len(levels) > 0 else []
        bids = levels[1] if len(levels) > 1 else []

        # Calculate derived metrics
        bid_levels = _parse_levels(bids)
        ask_levels = _parse_levels(asks)

        if bid_levels and ask_levels:
            spread = ask_levels[0]["px"] - bid_levels[0]["px"]
            mid_price = (ask_levels[0]["px"] + bid_levels[0]["px"]) / 2
        else:
            spread = 0
            mid_price = 0

        bid_depth = sum(level["sz"] for level in bid_levels)
        ask_depth = sum(level["sz"] for level in ask_levels)
        total_depth = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

        # Create document
        doc = {
            "t": datetime.utcnow(),
            "bids": bid_levels[:50],  # Top 50 levels
            "asks": ask_levels[:50],
            "spread": spread,
            "midPrice": mid_price,
            "bidDepth": bid_depth,
            "askDepth": ask_depth,
            "imbalance": imbalance,
            "createdAt": datetime.utcnow(),
        }

        # Insert into collection
        await collection.insert_one(doc)

        logger.debug(
            f"Collected orderbook: mid=${mid_price:.2f}, "
            f"spread=${spread:.2f}, imbalance={imbalance:.4f}"
        )

        return {
            "success": True,
            "midPrice": mid_price,
            "spread": spread,
            "imbalance": imbalance,
            "bidDepth": bid_depth,
            "askDepth": ask_depth,
        }

    except Exception as e:
        logger.error(f"Error collecting orderbook: {e}")
        return {"success": False, "error": str(e)}


def _parse_levels(levels: List) -> List[Dict]:
    """
    Parse orderbook levels from API response.

    Args:
        levels: Raw levels from API

    Returns:
        List of parsed level dictionaries
    """
    parsed = []
    for level in levels:
        try:
            parsed.append(
                {
                    "px": float(level.get("px", 0)),
                    "sz": float(level.get("sz", 0)),
                    "n": int(level.get("n", 0)),
                }
            )
        except (ValueError, TypeError):
            continue
    return parsed


async def get_orderbook_summary(
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Get the latest orderbook summary.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with orderbook summary
    """
    collection = db[CollectionName.BTC_ORDERBOOK]

    latest = await collection.find_one(sort=[("t", -1)])

    if not latest:
        return {"available": False}

    return {
        "available": True,
        "midPrice": latest.get("midPrice"),
        "spread": latest.get("spread"),
        "imbalance": latest.get("imbalance"),
        "bidDepth": latest.get("bidDepth"),
        "askDepth": latest.get("askDepth"),
        "timestamp": latest.get("t"),
    }


async def get_orderbook_history(
    db: AsyncIOMotorDatabase,
    hours: int = 24,
) -> List[Dict]:
    """
    Get orderbook history for the past hours.

    Args:
        db: MongoDB database
        hours: Number of hours to retrieve

    Returns:
        List of orderbook documents
    """
    collection = db[CollectionName.BTC_ORDERBOOK]

    from datetime import timedelta

    threshold = datetime.utcnow() - timedelta(hours=hours)

    cursor = collection.find(
        {"t": {"$gte": threshold}},
        {
            "t": 1,
            "midPrice": 1,
            "spread": 1,
            "imbalance": 1,
            "bidDepth": 1,
            "askDepth": 1,
        },
    ).sort("t", 1)

    return await cursor.to_list(length=None)
