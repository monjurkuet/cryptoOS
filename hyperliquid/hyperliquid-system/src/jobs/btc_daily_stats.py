"""
BTC Daily Stats Collection Job.

This module collects OI, liquidity, and liquidation data from CloudFront.
"""

from datetime import datetime
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.api.cloudfront import CloudFrontClient
from src.config import settings
from src.models.base import CollectionName


async def collect_daily_stats(
    client: CloudFrontClient,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store daily BTC stats (OI, liquidity, liquidations).

    Args:
        client: CloudFront API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    results = {
        "openInterest": 0,
        "liquidity": 0,
        "liquidations": 0,
    }

    try:
        # Collect Open Interest
        oi_count = await _collect_open_interest(client, db)
        results["openInterest"] = oi_count

        # Collect Liquidity
        liq_count = await _collect_liquidity(client, db)
        results["liquidity"] = liq_count

        # Collect Liquidations
        liqs_count = await _collect_liquidations(client, db)
        results["liquidations"] = liqs_count

        logger.info(
            f"Collected daily stats: OI={oi_count}, "
            f"liquidity={liq_count}, liquidations={liqs_count}"
        )

        return {"success": True, **results}

    except Exception as e:
        logger.error(f"Error collecting daily stats: {e}")
        return {"success": False, "error": str(e), **results}


async def _collect_open_interest(
    client: CloudFrontClient,
    db: AsyncIOMotorDatabase,
) -> int:
    """Collect BTC open interest data."""
    collection = db[CollectionName.BTC_OPEN_INTEREST]

    try:
        data = await client.get_open_interest()
        btc_records = CloudFrontClient.filter_btc(data)

        count = 0
        for record in btc_records:
            date_str = record.get("time", "").split("T")[0]
            if not date_str:
                continue

            doc = {
                "date": date_str,
                "openInterest": record.get("open_interest", 0),
                "createdAt": datetime.utcnow(),
            }

            await collection.update_one(
                {"date": date_str},
                {"$set": doc},
                upsert=True,
            )
            count += 1

        return count

    except Exception as e:
        logger.error(f"Error collecting OI: {e}")
        return 0


async def _collect_liquidity(
    client: CloudFrontClient,
    db: AsyncIOMotorDatabase,
) -> int:
    """Collect BTC liquidity data."""
    collection = db[CollectionName.BTC_LIQUIDITY]

    try:
        data = await client.get_liquidity_by_coin()
        btc_records = CloudFrontClient.filter_btc(data)

        count = 0
        for record in btc_records:
            date_str = record.get("time", "").split("T")[0]
            if not date_str:
                continue

            doc = {
                "date": date_str,
                "midPrice": record.get("mid_price", 0),
                "medianLiquidity": record.get("median_liquidity", 0),
                "slippage1k": record.get("median_slippage_1000"),
                "slippage3k": record.get("median_slippage_3000"),
                "slippage10k": record.get("median_slippage_10000"),
                "slippage30k": record.get("median_slippage_30000"),
                "slippage100k": record.get("median_slippage_100000"),
                "createdAt": datetime.utcnow(),
            }

            await collection.update_one(
                {"date": date_str},
                {"$set": doc},
                upsert=True,
            )
            count += 1

        return count

    except Exception as e:
        logger.error(f"Error collecting liquidity: {e}")
        return 0


async def _collect_liquidations(
    client: CloudFrontClient,
    db: AsyncIOMotorDatabase,
) -> int:
    """Collect BTC liquidation data."""
    collection = db[CollectionName.BTC_LIQUIDATIONS]

    try:
        data = await client.get_daily_liquidations()
        btc_records = CloudFrontClient.filter_btc(data)

        count = 0
        for record in btc_records:
            date_str = record.get("time", "").split("T")[0]
            if not date_str:
                continue

            doc = {
                "date": date_str,
                "notionalLiquidated": record.get("daily_notional_liquidated", 0),
                "createdAt": datetime.utcnow(),
            }

            await collection.update_one(
                {"date": date_str},
                {"$set": doc},
                upsert=True,
            )
            count += 1

        return count

    except Exception as e:
        logger.error(f"Error collecting liquidations: {e}")
        return 0


async def get_open_interest_history(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> List[Dict]:
    """Get open interest history."""
    from datetime import timedelta

    collection = db[CollectionName.BTC_OPEN_INTEREST]
    threshold = datetime.utcnow() - timedelta(days=days)

    cursor = collection.find(
        {"createdAt": {"$gte": threshold}},
    ).sort("date", 1)

    return await cursor.to_list(length=None)


async def get_liquidation_history(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> List[Dict]:
    """Get liquidation history."""
    from datetime import timedelta

    collection = db[CollectionName.BTC_LIQUIDATIONS]
    threshold = datetime.utcnow() - timedelta(days=days)

    cursor = collection.find(
        {"createdAt": {"$gte": threshold}},
    ).sort("date", 1)

    return await cursor.to_list(length=None)
