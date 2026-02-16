"""
Database Setup Module.

This module handles MongoDB initialization, including creating collections and indexes.
"""

from typing import List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName, REGULAR_INDEXES, TIMESERIES_INDEXES


async def setup_database(db: AsyncIOMotorDatabase) -> None:
    """
    Set up all collections and indexes.

    Args:
        db: MongoDB database instance
    """
    logger.info(f"Setting up database: {db.name}")

    # Create time-series collections
    await _create_timeseries_collections(db)

    # Create regular collections with indexes
    await _create_regular_collections(db)

    logger.info("Database setup complete")


async def _create_timeseries_collections(db: AsyncIOMotorDatabase) -> None:
    """Create time-series collections with appropriate settings."""

    # Define time-series collection configurations
    timeseries_configs = {
        CollectionName.BTC_CANDLES: {
            "timeField": "t",
            "metaField": "interval",
            "granularity": "minutes",
        },
        CollectionName.BTC_ORDERBOOK: {
            "timeField": "t",
            "metaField": None,
            "granularity": "seconds",
        },
        CollectionName.BTC_TRADES: {
            "timeField": "t",
            "metaField": None,
            "granularity": "seconds",
        },
        CollectionName.TRADER_POSITIONS: {
            "timeField": "t",
            "metaField": "ethAddress",
            "granularity": "seconds",
        },
        CollectionName.TRADER_ORDERS: {
            "timeField": "timestamp",
            "metaField": "ethAddress",
            "granularity": "seconds",
        },
        CollectionName.BTC_SIGNALS: {
            "timeField": "t",
            "metaField": "signalType",
            "granularity": "seconds",
        },
        CollectionName.LEADERBOARD_HISTORY: {
            "timeField": "t",
            "metaField": None,
            "granularity": "hours",
        },
    }

    for collection_name, config in timeseries_configs.items():
        try:
            # Check if collection exists
            collections = await db.list_collection_names()

            if collection_name in collections:
                logger.debug(f"Collection {collection_name} already exists")
            else:
                # Create time-series collection
                await db.create_collection(
                    collection_name,
                    timeseries={
                        "timeField": config["timeField"],
                        "metaField": config["metaField"],
                        "granularity": config["granularity"],
                    },
                )
                logger.info(f"Created time-series collection: {collection_name}")

            # Create indexes
            indexes = TIMESERIES_INDEXES.get(collection_name, [])
            await _create_indexes(db, collection_name, indexes)

        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")


async def _create_regular_collections(db: AsyncIOMotorDatabase) -> None:
    """Create regular collections with indexes."""

    regular_collections = [
        CollectionName.BTC_TICKER,
        CollectionName.BTC_FUNDING,
        CollectionName.BTC_OPEN_INTEREST,
        CollectionName.BTC_LIQUIDITY,
        CollectionName.BTC_LIQUIDATIONS,
        CollectionName.TRACKED_TRADERS,
        CollectionName.TRADER_CURRENT_STATE,
    ]

    for collection_name in regular_collections:
        try:
            # Check if collection exists
            collections = await db.list_collection_names()

            if collection_name not in collections:
                # Collection will be created on first insert
                logger.debug(f"Collection {collection_name} will be created on first insert")

            # Create indexes
            indexes = REGULAR_INDEXES.get(collection_name, [])
            await _create_indexes(db, collection_name, indexes)

        except Exception as e:
            logger.error(f"Error setting up collection {collection_name}: {e}")


async def _create_indexes(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    indexes: List[dict],
) -> None:
    """Create indexes for a collection."""

    if not indexes:
        return

    collection = db[collection_name]

    for index_config in indexes:
        try:
            keys = index_config["keys"]
            options = {k: v for k, v in index_config.items() if k != "keys"}

            await collection.create_index(keys, **options)
            logger.debug(f"Created index on {collection_name}: {keys}")
        except Exception as e:
            # Ignore duplicate index errors
            if "already exists" not in str(e).lower():
                logger.warning(f"Error creating index on {collection_name}: {e}")


async def get_database() -> AsyncIOMotorDatabase:
    """
    Get database connection.

    Returns:
        MongoDB database instance
    """
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]
    return db


async def check_database_connection(db: AsyncIOMotorDatabase) -> bool:
    """
    Check database connection.

    Args:
        db: MongoDB database instance

    Returns:
        True if connection is successful
    """
    try:
        await db.command("ping")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def get_collection_stats(db: AsyncIOMotorDatabase) -> dict:
    """
    Get statistics for all collections.

    Args:
        db: MongoDB database instance

    Returns:
        Dictionary with collection statistics
    """
    stats = {}

    collections = await db.list_collection_names()

    for collection_name in collections:
        try:
            count = await db[collection_name].count_documents({})
            stats[collection_name] = {"count": count}
        except Exception:
            stats[collection_name] = {"count": 0}

    return stats
