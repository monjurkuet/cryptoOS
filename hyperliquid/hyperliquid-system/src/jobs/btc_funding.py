"""
BTC Funding Collection Job.

This module collects funding rate history for BTC.
"""

from datetime import datetime
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


async def collect_funding(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC funding rate history.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    collection = db[CollectionName.BTC_FUNDING]

    try:
        # Fetch funding history from API
        funding_data = await client.get_funding_history(settings.target_coin)

        if not funding_data:
            logger.warning("No funding data received")
            return {"success": False, "error": "No data", "new_records": 0}

        # Get existing timestamps
        existing = await collection.distinct("t")
        existing_ts = set(existing)

        # Prepare new documents
        documents = []
        for record in funding_data:
            t = datetime.utcfromtimestamp(record.get("time", 0) / 1000)

            # Skip if already exists
            if t in existing_ts:
                continue

            delta = record.get("delta", {})

            doc = {
                "t": t,
                "fundingRate": float(delta.get("fundingRate", 0)),
                "nextFundingTime": None,  # Will be calculated
                "createdAt": datetime.utcnow(),
            }
            documents.append(doc)

        if not documents:
            logger.debug("No new funding records to insert")
            return {"success": True, "new_records": 0}

        # Insert documents
        await collection.insert_many(documents)

        logger.info(f"Collected {len(documents)} new funding records")

        return {
            "success": True,
            "new_records": len(documents),
        }

    except Exception as e:
        logger.error(f"Error collecting funding: {e}")
        return {"success": False, "error": str(e), "new_records": 0}


async def get_funding_history(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> List[Dict]:
    """
    Get funding rate history for the past N days.

    Args:
        db: MongoDB database
        days: Number of days to retrieve

    Returns:
        List of funding records
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_FUNDING]
    threshold = datetime.utcnow() - timedelta(days=days)

    cursor = collection.find(
        {"t": {"$gte": threshold}},
        {"t": 1, "fundingRate": 1},
    ).sort("t", 1)

    return await cursor.to_list(length=None)


async def get_current_funding(
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Get the most recent funding rate.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with current funding data
    """
    collection = db[CollectionName.BTC_FUNDING]

    latest = await collection.find_one(sort=[("t", -1)])

    if not latest:
        return {"available": False}

    return {
        "available": True,
        "fundingRate": latest.get("fundingRate"),
        "timestamp": latest.get("t"),
    }


async def get_funding_summary(
    db: AsyncIOMotorDatabase,
    days: int = 7,
) -> Dict:
    """
    Get funding rate summary for the past N days.

    Args:
        db: MongoDB database
        days: Number of days to analyze

    Returns:
        Dictionary with funding summary
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_FUNDING]
    threshold = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"t": {"$gte": threshold}}},
        {
            "$group": {
                "_id": None,
                "count": {"$sum": 1},
                "avgRate": {"$avg": "$fundingRate"},
                "maxRate": {"$max": "$fundingRate"},
                "minRate": {"$min": "$fundingRate"},
                "positiveCount": {"$sum": {"$cond": [{"$gt": ["$fundingRate", 0]}, 1, 0]}},
                "negativeCount": {"$sum": {"$cond": [{"$lt": ["$fundingRate", 0]}, 1, 0]}},
            }
        },
    ]

    result = await collection.aggregate(pipeline).to_list(length=1)

    if not result:
        return {
            "available": False,
            "count": 0,
            "avgRate": 0,
            "maxRate": 0,
            "minRate": 0,
        }

    summary = result[0]
    del summary["_id"]
    summary["available"] = True

    return summary
