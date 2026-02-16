"""
BTC Ticker Update Job.

This module updates the BTC ticker (24h statistics).
"""

from datetime import datetime
from typing import Dict

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


async def update_ticker(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Update BTC ticker with latest 24h statistics.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with update results
    """
    collection = db[CollectionName.BTC_TICKER]

    try:
        # Fetch ticker from API (uses metaAndAssetCtxs)
        ticker_data = await client.get_ticker(settings.target_coin)

        if not ticker_data:
            logger.warning("No ticker data received")
            return {"success": False, "error": "No data"}

        # Create document with new field names
        doc = {
            "_id": "btc_ticker",
            "t": datetime.utcnow(),
            "px": float(ticker_data.get("markPx", 0)),
            "midPx": float(ticker_data.get("midPx", 0)),
            "oraclePx": float(ticker_data.get("oraclePx", 0)),
            "prevDayPx": float(ticker_data.get("prevDayPx", 0)),
            "volume24h": float(ticker_data.get("dayNtlVlm", 0)),
            "volumeBase24h": float(ticker_data.get("dayBaseVlm", 0)),
            "funding": float(ticker_data.get("funding", 0)),
            "openInterest": float(ticker_data.get("openInterest", 0)),
            "premium": float(ticker_data.get("premium", 0)),
            "maxLeverage": int(ticker_data.get("maxLeverage", 0)),
            "updatedAt": datetime.utcnow(),
        }

        # Upsert ticker
        await collection.replace_one(
            {"_id": "btc_ticker"},
            doc,
            upsert=True,
        )

        logger.debug(f"Updated ticker: ${doc['px']:.2f}, 24h vol=${doc['volume24h']:,.0f}")

        return {
            "success": True,
            "price": doc["px"],
            "volume24h": doc["volume24h"],
            "funding": doc["funding"],
            "openInterest": doc["openInterest"],
        }

    except Exception as e:
        logger.error(f"Error updating ticker: {e}")
        return {"success": False, "error": str(e)}


async def get_current_ticker(
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Get the current BTC ticker.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with ticker data
    """
    collection = db[CollectionName.BTC_TICKER]

    ticker = await collection.find_one({"_id": "btc_ticker"})

    if not ticker:
        return {"available": False}

    return {
        "available": True,
        "price": ticker.get("px"),
        "volume24h": ticker.get("volume24h"),
        "trades24h": ticker.get("trades24h"),
        "high24h": ticker.get("high24h"),
        "low24h": ticker.get("low24h"),
        "updatedAt": ticker.get("updatedAt"),
    }


async def get_current_price(
    db: AsyncIOMotorDatabase,
) -> float:
    """
    Get the current BTC price.

    Args:
        db: MongoDB database

    Returns:
        Current BTC price or 0 if not available
    """
    ticker = await get_current_ticker(db)
    return ticker.get("price", 0) if ticker.get("available") else 0
