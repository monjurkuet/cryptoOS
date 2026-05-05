"""MongoDB repository implementation for the Market Scraper Framework."""

from datetime import UTC, datetime
from typing import Any

import asyncio

import motor.motor_asyncio
import pymongo
import structlog
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.core.types import Symbol, Timeframe
from market_scraper.storage.base import DataRepository, QueryFilter
from market_scraper.storage.models import (
    Candle,
    CollectionName,
    TrackedTrader,
    TraderClosedTrade,
    TraderPosition,
    TraderScore,
    TraderSignal,
    TradingSignal,
)

logger = structlog.get_logger(__name__)


class MongoRepository(DataRepository):
    """MongoDB implementation of DataRepository.

    Uses Motor for async MongoDB operations.
    Collections: events, ohlcv, metadata

    Indexes created:
    - Compound: (timestamp: -1, event_type: 1, source: 1)
    - Compound: (payload.symbol: 1, timestamp: -1)
    - Single: correlation_id
    - Single: event_id (unique)
    """

    def __init__(
        self,
        connection_string: str,
        database_name: str = "market_scraper",
    ) -> None:
        """Initialize MongoDB repository.

        Args:
            connection_string: MongoDB connection string.
            database_name: Name of the database to use.
        """
        super().__init__(connection_string)
        self._database_name = database_name
        # Async Motor client (for reads and index creation)
        self._client: motor.motor_asyncio.AsyncIOMotorClient | None = None
        self._db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None
        # Sync pymongo client (for writes via asyncio.to_thread — avoids event-loop blocking)
        self._sync_client: pymongo.MongoClient | None = None
        self._sync_db: pymongo.database.Database | None = None

    async def connect(self) -> None:
        """Connect to MongoDB.

        Raises:
            StorageError: If connection fails.
        """
        start_time = datetime.now(UTC)
        logger.info("mongodb_connecting", database=self._database_name)

        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(
                self._connection_string,
                maxPoolSize=10,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=30000,
                waitQueueTimeoutMS=10000,
                connectTimeoutMS=10000,
            )
            self._db = self._client[self._database_name]

            # Sync pymongo client for writes (runs in thread pool, never blocks event loop)
            self._sync_client = pymongo.MongoClient(
                self._connection_string,
                maxPoolSize=4,
                minPoolSize=1,
                serverSelectionTimeoutMS=5000,
                socketTimeoutMS=15000,
                waitQueueTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
            self._sync_db = self._sync_client[self._database_name]

            self._connected = True

            # Create indexes
            await self._create_indexes()

            duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.info("mongodb_connected", duration_ms=round(duration_ms, 2))
        except Exception as e:
            logger.error("mongodb_connect_failed", error=str(e), exc_info=True)
            raise StorageError(f"Failed to connect to MongoDB: {e}") from e

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._sync_client:
            self._sync_client.close()
        if self._client:
            self._client.close()
            logger.info("mongodb_disconnected")
        self._connected = False
        self._client = None
        self._db = None
        self._sync_client = None
        self._sync_db = None

    async def _create_indexes(self) -> None:
        """Create necessary indexes for optimal query performance."""
        if self._db is None:
            return

        events = self._db.events

        # Compound index for common query patterns (time-based with filtering)
        await events.create_index(
            [
                ("timestamp", -1),
                ("event_type", 1),
                ("source", 1),
            ]
        )

        # Compound index for symbol-based queries
        await events.create_index(
            [
                ("payload.symbol", 1),
                ("timestamp", -1),
            ]
        )

        # Index for correlation tracking
        await events.create_index("correlation_id")

        # Unique index for event deduplication
        await events.create_index("event_id", unique=True)

        # ============== TTL Indexes for Retention ==============
        await self._create_ttl_indexes()

        # ============== Query Performance Indexes ==============
        await self._create_model_indexes()

    async def _create_ttl_indexes(self) -> None:
        """Create TTL indexes for automatic data retention.

        Handles IndexOptionsConflict (code 85) by dropping conflicting
        old indexes (e.g. legacy 'ttl_retention' without collection suffix)
        and retrying creation.
        """
        if self._db is None:
            return

        retention = self._get_retention_config()

        # Global collections with TTL indexes
        ttl_collections = [
            ("events", "timestamp", retention.events),
            (CollectionName.LEADERBOARD_HISTORY, "t", retention.leaderboard_history),
            (CollectionName.TRADER_POSITIONS, "t", retention.trader_positions),
            (CollectionName.TRADER_CLOSED_TRADES, "t", retention.trader_closed_trades),
            (CollectionName.TRADER_SCORES, "t", retention.trader_scores),
            (CollectionName.SIGNALS, "t", retention.signals),
            (CollectionName.TRADER_SIGNALS, "t", retention.trader_signals),
            (CollectionName.MARK_PRICES, "t", retention.mark_prices),
            ("dead_letters", "timestamp", 7),
        ]

        for collection_name, field, days in ttl_collections:
            target_name = f"ttl_retention_{collection_name}"
            for attempt in range(2):  # max 2 attempts (initial + retry after drop)
                try:
                    await self._db[collection_name].create_index(
                        [(field, 1)],
                        name=target_name,
                        expireAfterSeconds=days * 86400,
                    )
                    logger.info(
                        "ttl_index_created",
                        collection=collection_name,
                        retention_days=days,
                    )
                    break  # success, move to next collection
                except OperationFailure as e:
                    # In pymongo 4.x, IndexOptionsConflict is now OperationFailure(code=85)
                    if e.code != 85:
                        raise  # Not an index conflict, re-raise to outer handler
                    # An old index with a different name/options exists on the same key.
                    # Drop the conflicting index and retry.
                    logger.warning(
                        "ttl_index_conflict_dropping_old",
                        collection=collection_name,
                        error=str(e),
                    )
                    try:
                        # List indexes to find the conflicting one
                        async for idx in self._db[collection_name].list_indexes():
                            idx_name = idx.get("name", "")
                            idx_key = idx.get("key", {})
                            # Drop old 'ttl_retention' index (without collection suffix)
                            # or any TTL index on the same field that isn't our target
                            if (
                                idx_name != target_name
                                and idx.get("expireAfterSeconds") is not None
                            ):
                                # Check if it's on the same key field
                                if field in idx_key:
                                    await self._db[collection_name].drop_index(
                                        idx_name
                                    )
                                    logger.info(
                                        "ttl_index_dropped_old",
                                        collection=collection_name,
                                        dropped_index=idx_name,
                                    )
                    except Exception as drop_err:
                        logger.error(
                            "ttl_index_drop_failed",
                            collection=collection_name,
                            error=str(drop_err),
                        )
                    # Retry index creation on next loop iteration
                    continue
                except Exception as e:
                    logger.warning(
                        "ttl_index_creation_failed",
                        collection=collection_name,
                        error=str(e),
                    )
                    break  # non-retryable error, move on

    async def _create_model_indexes(self) -> None:
        """Create query performance indexes for model-specific collections."""
        if self._db is None:
            return

        try:
            # Trader positions - compound index for efficient queries
            await self._db[CollectionName.TRADER_POSITIONS].create_index(
                [("eth", 1), ("coin", 1), ("t", -1)]
            )

            # Trader scores - compound index
            await self._db[CollectionName.TRADER_SCORES].create_index([("eth", 1), ("t", -1)])

            # Tracked traders - unique index on eth address
            await self._db[CollectionName.TRACKED_TRADERS].create_index([("eth", 1)], unique=True)
            await self._db[CollectionName.TRACKED_TRADERS].create_index([("score", -1)])
            await self._db[CollectionName.TRACKED_TRADERS].create_index([("active", 1)])

            # Trader current state - latest materialized snapshot per trader/symbol
            await self._db[CollectionName.TRADER_CURRENT_STATE].create_index(
                [("eth", 1), ("symbol", 1)],
                unique=True,
            )
            # Legacy compatibility during migration: keep ethAddress lookups indexed
            await self._db[CollectionName.TRADER_CURRENT_STATE].create_index(
                [("ethAddress", 1), ("symbol", 1)]
            )
            await self._db[CollectionName.TRADER_CURRENT_STATE].create_index([("updated_at", -1)])

            await self._db[CollectionName.TRADER_CLOSED_TRADES].create_index(
                [("eth", 1), ("symbol", 1), ("t", -1)]
            )
            await self._db[CollectionName.TRADER_CLOSED_TRADES].create_index(
                [("trade_id", 1)],
                unique=True,
            )

            # Signals - symbol and time
            await self._db[CollectionName.SIGNALS].create_index([("symbol", 1), ("t", -1)])

        # Trader signals - compound indexes
            await self._db[CollectionName.TRADER_SIGNALS].create_index([("eth", 1), ("t", -1)])
            await self._db[CollectionName.TRADER_SIGNALS].create_index([("symbol", 1), ("t", -1)])

            logger.info("model_indexes_created")
        except Exception as e:
            logger.warning("model_index_creation_failed", error=str(e), exc_info=True)

    def _get_retention_config(self) -> Any:
        """Get retention configuration from traders config."""
        try:
            from market_scraper.config.market_config import load_market_config

            config = load_market_config()
            return config.storage.retention
        except Exception as e:
            # Return default retention config
            logger.debug("retention_config_fallback", error=str(e))
            from market_scraper.config.market_config import RetentionConfig

            return RetentionConfig()

    @staticmethod
    def _normalize_tags(tags: Any) -> list[str]:
        """Normalize tag collections for stable equality comparisons."""
        return sorted(str(tag) for tag in (tags or []))

    @staticmethod
    def _normalize_mapping(value: Any) -> dict[str, Any]:
        """Normalize mapping values for stable persistence comparisons."""
        return dict(value or {})

    @staticmethod
    def _position_snapshot_payload(position: TraderPosition | dict[str, Any]) -> dict[str, Any]:
        """Build comparable payload for trader position history rows."""
        data = position.model_dump() if hasattr(position, "model_dump") else dict(position)
        return {
            "eth": str(data.get("eth", "")).lower(),
            "coin": str(data.get("coin", "")),
            "sz": float(data.get("sz", 0) or 0),
            "ep": float(data.get("ep", 0) or 0),
            "lev": float(data.get("lev", 0) or 0),
            "liq": data.get("liq"),
        }

    @staticmethod
    def _score_snapshot_payload(score: TraderScore | dict[str, Any]) -> dict[str, Any]:
        """Build comparable payload for trader score history rows."""
        data = score.model_dump() if hasattr(score, "model_dump") else dict(score)
        return {
            "eth": str(data.get("eth", "")).lower(),
            "score": float(data.get("score", 0) or 0),
            "tags": MongoRepository._normalize_tags(data.get("tags")),
            "acct_val": float(data.get("acct_val", 0) or 0),
            "all_roi": float(data.get("all_roi", 0) or 0),
            "month_roi": float(data.get("month_roi", 0) or 0),
            "week_roi": float(data.get("week_roi", 0) or 0),
        }

    @classmethod
    def _current_state_payload(
        cls,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
        existing_state: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Build comparable payload for materialized trader current state."""
        return cls.build_trader_current_state_payload(
            address=address,
            symbol=symbol,
            positions=positions,
            open_orders=open_orders,
            margin_summary=margin_summary,
            event_timestamp=event_timestamp,
            source=source,
            existing_state=existing_state,
        )

    async def store(self, event: StandardEvent) -> bool:
        """Store a single event.

        Args:
            event: Event to store.

        Returns:
            True if stored successfully, False if duplicate.

        Raises:
            StorageError: If not connected or storage fails (excluding duplicates).
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            doc = event.model_dump()
            doc.pop("payload", None)
            result = await asyncio.to_thread(self._sync_store, doc)
            return result
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store event: {e}") from e

    def _sync_store(self, doc: dict) -> bool:
        """Sync implementation of store (runs in thread pool)."""
        try:
            self._sync_db.events.insert_one(doc)
            return True
        except DuplicateKeyError:
            logger.debug(
                "event_duplicate_skipped",
                event_id=doc.get("event_id"),
            )
            return False

    async def store_bulk(self, events: list[StandardEvent]) -> int:
        """Store multiple events efficiently.

        Uses insert_many for better performance.
        Handles duplicate key errors gracefully.

        Args:
            events: List of events to store.

        Returns:
            Number of events stored.

        Raises:
            StorageError: If not connected.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        if not events:
            return 0

        try:
            documents = [{k: v for k, v in e.model_dump().items() if k != "payload"} for e in events]
            return await asyncio.to_thread(self._sync_store_bulk, documents)
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store bulk events: {e}") from e

    def _sync_store_bulk(self, documents: list[dict]) -> int:
        """Sync implementation of store_bulk (runs in thread pool)."""
        try:
            result = self._sync_db.events.insert_many(documents, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as e:
            n_inserted = e.details.get("nInserted", 0)
            n_duplicates = sum(
                1 for err in e.details.get("writeErrors", [])
                if err.get("code") == 11000
            )
            if n_duplicates > 0:
                logger.debug(
                    "store_bulk_duplicates_skipped",
                    inserted=n_inserted,
                    duplicates=n_duplicates,
                )
            return n_inserted

    async def query(
        self,
        filter_: QueryFilter,
    ) -> list[StandardEvent]:
        """Query events with filters.

        Args:
            filter_: Query filter criteria.

        Returns:
            List of matching events.

        Raises:
            StorageError: If not connected or query fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        query: dict[str, Any] = {}

        if filter_.symbol:
            query["payload.symbol"] = filter_.symbol
        if filter_.event_type:
            query["event_type"] = filter_.event_type
        if filter_.source:
            query["source"] = filter_.source
        if filter_.start_time or filter_.end_time:
            query["timestamp"] = {}
            if filter_.start_time:
                query["timestamp"]["$gte"] = filter_.start_time
            if filter_.end_time:
                query["timestamp"]["$lte"] = filter_.end_time

        cursor = self._db.events.find(query)
        cursor = cursor.sort("timestamp", -1)
        cursor = cursor.skip(filter_.offset).limit(filter_.limit)

        events = []
        async for doc in cursor:
            # Remove MongoDB _id field
            doc.pop("_id", None)
            events.append(StandardEvent.model_validate(doc))

        return events

    async def get_latest(
        self,
        symbol: Symbol,
        event_type: str,
        source: str | None = None,
    ) -> StandardEvent | None:
        """Get the most recent event for a symbol.

        Args:
            symbol: Trading symbol.
            event_type: Type of event.
            source: Optional source filter.

        Returns:
            Most recent event or None if not found.

        Raises:
            StorageError: If not connected or query fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        query: dict[str, Any] = {
            "payload.symbol": symbol,
            "event_type": event_type,
        }
        if source:
            query["source"] = source

        doc = await self._db.events.find_one(
            query,
            sort=[("timestamp", -1)],
        )

        if doc:
            doc.pop("_id", None)
            return StandardEvent.model_validate(doc)
        return None

    async def aggregate_ohlcv(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Aggregate trade events into OHLCV candles.

        Uses MongoDB aggregation pipeline for efficient computation.

        Args:
            symbol: Trading symbol.
            timeframe: Candle timeframe (e.g., "1m", "1h").
            start: Start time.
            end: End time.

        Returns:
            List of OHLCV data points.

        Raises:
            StorageError: If not connected or aggregation fails.
            ValueError: If timeframe is not supported.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        # Parse timeframe to milliseconds
        if timeframe.endswith("s"):
            interval_ms = int(timeframe[:-1]) * 1000
        elif timeframe.endswith("m"):
            interval_ms = int(timeframe[:-1]) * 60 * 1000
        elif timeframe.endswith("h"):
            interval_ms = int(timeframe[:-1]) * 60 * 60 * 1000
        elif timeframe.endswith("d"):
            interval_ms = int(timeframe[:-1]) * 60 * 60 * 24 * 1000
        elif timeframe.endswith("w"):
            interval_ms = int(timeframe[:-1]) * 60 * 60 * 24 * 7 * 1000
        elif timeframe == "1M":
            interval_ms = 30 * 24 * 60 * 60 * 1000  # Approximate month
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        pipeline = [
            {
                "$match": {
                    "payload.symbol": symbol,
                    "event_type": "trade",
                    "timestamp": {"$gte": start, "$lte": end},
                }
            },
            {
                "$group": {
                    "_id": {
                        "$toDate": {
                            "$subtract": [
                                {"$toLong": "$timestamp"},
                                {
                                    "$mod": [
                                        {"$toLong": "$timestamp"},
                                        interval_ms,
                                    ]
                                },
                            ]
                        }
                    },
                    "open": {"$first": "$payload.price"},
                    "high": {"$max": "$payload.price"},
                    "low": {"$min": "$payload.price"},
                    "close": {"$last": "$payload.price"},
                    "volume": {"$sum": {"$ifNull": ["$payload.volume", 0]}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        try:
            cursor = self._db.events.aggregate(pipeline)
            results = []

            async for doc in cursor:
                results.append(
                    {
                        "timestamp": doc["_id"],
                        "open": doc["open"],
                        "high": doc["high"],
                        "low": doc["low"],
                        "close": doc["close"],
                        "volume": doc["volume"],
                        "count": doc["count"],
                    }
                )

            return results
        except Exception as e:
            raise StorageError(f"Failed to aggregate OHLCV: {e}") from e

    async def health_check(self) -> dict:
        """Check MongoDB health.

        Performs ping command and retrieves collection stats.

        Returns:
            Health status dict with:
            - status: "healthy" or "unhealthy"
            - latency_ms: Response time in milliseconds
            - document_count: Number of documents in events collection
            - storage_size_mb: Size of events collection in MB
        """
        if self._db is None:
            return {
                "status": "unhealthy",
                "error": "Not connected to MongoDB",
            }

        try:
            start = datetime.now(UTC)
            await self._db.command("ping")
            latency = (datetime.now(UTC) - start).total_seconds() * 1000

            # Get collection stats
            try:
                stats = await self._db.command("collstats", "events")
                doc_count = stats.get("count", 0)
                storage_size = stats.get("size", 0) / (1024 * 1024)
            except Exception as e:
                # Collection might not exist yet
                logger.debug("health_check_collstats_error", error=str(e))
                doc_count = 0
                storage_size = 0.0

            return {
                "status": "healthy",
                "latency_ms": latency,
                "document_count": doc_count,
                "storage_size_mb": storage_size,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def drop_collection(self, collection_name: str) -> None:
        """Drop a collection (useful for testing).

        Args:
            collection_name: Name of collection to drop.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        await self._db[collection_name].drop()

    # ============== Model-Specific Methods ==============

    async def store_candle(self, candle: Candle, symbol: str, interval: str) -> bool:
        """Store a candle.

        Uses sync pymongo via asyncio.to_thread() to avoid blocking the event loop
        on remote Atlas writes.

        Args:
            candle: Candle to store.
            symbol: Trading symbol.
            interval: Candle interval (e.g., "1m", "5m").

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            return await asyncio.to_thread(
                self._sync_store_candle, candle, symbol, interval
            )
        except Exception as e:
            raise StorageError(f"Failed to store candle: {e}") from e

    def _sync_store_candle(self, candle: Candle, symbol: str, interval: str) -> bool:
        """Sync implementation of store_candle (runs in thread pool)."""
        collection = self._sync_db[CollectionName.candles(symbol, interval)]
        collection.update_one(
            {"t": candle.t},
            {"$set": candle.model_dump()},
            upsert=True,
        )
        return True

    async def store_candles_bulk(
        self,
        candles: list[Candle],
        symbol: str,
        interval: str,
    ) -> int:
        """Store multiple candles efficiently using bulk write with upsert.

        Uses sync pymongo via asyncio.to_thread() to avoid blocking the event loop.

        Args:
            candles: List of candles to store
            symbol: Trading symbol (e.g., "BTC")
            interval: Candle interval (e.g., "1h")

        Returns:
            Number of candles inserted/modified

        Raises:
            StorageError: If not connected or storage fails
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        if not candles:
            return 0

        try:
            return await asyncio.to_thread(
                self._sync_store_candles_bulk, candles, symbol, interval
            )
        except Exception as e:
            raise StorageError(f"Failed to store candles bulk: {e}") from e

    def _sync_store_candles_bulk(
        self, candles: list[Candle], symbol: str, interval: str
    ) -> int:
        """Sync implementation of store_candles_bulk (runs in thread pool)."""

        collection = self._sync_db[CollectionName.candles(symbol, interval)]
        operations = [
            UpdateOne(
                {"t": candle.t},
                {"$set": candle.model_dump()},
                upsert=True,
            )
            for candle in candles
        ]
        result = collection.bulk_write(operations, ordered=False)
        return result.upserted_count + result.modified_count

    async def get_latest_candle(self, symbol: str, interval: str) -> dict[str, Any] | None:
        """Get the latest candle for a symbol and interval.

        Args:
            symbol: Trading symbol.
            interval: Candle interval.

        Returns:
            Latest candle dict or None if not found.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.candles(symbol, interval)]
            doc = await collection.find_one(sort=[("t", -1)])
            if doc:
                doc.pop("_id", None)
                return doc
            return None
        except Exception as e:
            raise StorageError(f"Failed to get latest candle: {e}") from e

    async def get_candles(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get historical candles for a symbol and interval.

        Args:
            symbol: Trading symbol.
            interval: Candle interval (e.g., "1m", "5m", "1h", "1d").
            start_time: Optional start time filter.
            end_time: Optional end time filter.
            limit: Maximum results.

        Returns:
            List of candle dictionaries.

        Raises:
            StorageError: If query fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.candles(symbol, interval)]

            query: dict[str, Any] = {}
            if start_time or end_time:
                query["t"] = {}
                if start_time:
                    query["t"]["$gte"] = start_time
                if end_time:
                    query["t"]["$lte"] = end_time

            cursor = collection.find(query)
            cursor = cursor.sort("t", -1).limit(min(limit, 10000))

            candles = []
            async for doc in cursor:
                doc.pop("_id", None)
                candles.append(doc)

            # Return in chronological order (oldest first)
            return list(reversed(candles))
        except Exception as e:
            raise StorageError(f"Failed to get candles: {e}") from e

    async def store_trader_position(self, position: TraderPosition) -> bool:
        """Store a trader position snapshot.

        Args:
            position: Position to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            normalized = position.model_dump()
            normalized["eth"] = str(normalized.get("eth", "")).lower()
            comparable = self._position_snapshot_payload(normalized)

            return await asyncio.to_thread(
                self._sync_store_trader_position, normalized, comparable
            )
        except Exception as e:
            raise StorageError(f"Failed to store position: {e}") from e

    def _sync_store_trader_position(
        self, normalized: dict, comparable: dict
    ) -> bool:
        """Sync implementation of store_trader_position (runs in thread pool)."""
        collection = self._sync_db[CollectionName.TRADER_POSITIONS]
        latest = collection.find_one(
            {"eth": comparable["eth"], "coin": comparable["coin"]},
            {
                "_id": 0, "eth": 1, "coin": 1, "sz": 1,
                "ep": 1, "mp": 1, "upnl": 1, "lev": 1, "liq": 1,
            },
            sort=[("t", -1)],
        )
        if latest and self._position_snapshot_payload(latest) == comparable:
            return True
        collection.insert_one(normalized)
        return True

    async def store_trader_position_bulk(self, positions: list[TraderPosition]) -> int:
        """Bulk-store trader position snapshots with a single insert_many call.

        Skips per-document find_one dedup checks — the TTL index handles cleanup
        and duplicate positions are acceptable in time-series collections.

        Args:
            positions: List of TraderPosition models to store.

        Returns:
            Count of inserted documents.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        if not positions:
            return 0

        try:
            documents = []
            for position in positions:
                normalized = position.model_dump()
                normalized["eth"] = str(normalized.get("eth", "")).lower()
                documents.append(normalized)

            return await asyncio.to_thread(
                self._sync_store_trader_position_bulk, documents
            )
        except Exception as e:
            raise StorageError(f"Failed to bulk-store positions: {e}") from e

    def _sync_store_trader_position_bulk(self, documents: list[dict]) -> int:
        """Sync implementation of store_trader_position_bulk (runs in thread pool)."""
        from pymongo.errors import BulkWriteError as SyncBulkWriteError

        collection = self._sync_db[CollectionName.TRADER_POSITIONS]
        try:
            result = collection.insert_many(documents, ordered=False)
            return len(result.inserted_ids)
        except SyncBulkWriteError:
            # Partial failures (e.g. duplicate _id) are acceptable for
            # time-series data — the TTL index handles cleanup.
            return len(documents)

    async def store_trader_closed_trade(self, trade: TraderClosedTrade | dict[str, Any]) -> bool:
        """Store a closed-trade ledger row idempotently."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_CLOSED_TRADES]
            normalized = (
                trade.model_dump()
                if hasattr(trade, "model_dump")
                else TraderClosedTrade.model_validate(trade).model_dump()
            )
            normalized["eth"] = str(normalized.get("eth", "")).lower()
            normalized["symbol"] = str(normalized.get("symbol", "")).upper()

            await collection.update_one(
                {"trade_id": normalized["trade_id"]},
                {"$setOnInsert": normalized},
                upsert=True,
            )
            return True
        except DuplicateKeyError:
            return True
        except Exception as e:
            raise StorageError(f"Failed to store closed trade: {e}") from e

    async def get_trader_positions(
        self,
        address: str,
        symbol: str,
        limit: int = 100,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[TraderPosition]:
        """Get position history for a trader.

        Args:
            address: Trader Ethereum address.
            symbol: Trading symbol.
            limit: Maximum results.
            start: Start time filter.
            end: End time filter.

        Returns:
            List of positions.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_POSITIONS]
            query: dict[str, Any] = {"eth": address, "coin": symbol}

            if start or end:
                query["t"] = {}
                if start:
                    query["t"]["$gte"] = start
                if end:
                    query["t"]["$lte"] = end

            cursor = collection.find(query).sort("t", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            positions = []
            for doc in docs:
                doc.pop("_id", None)
                positions.append(TraderPosition.model_validate(doc))
            return positions
        except Exception as e:
            raise StorageError(f"Failed to get trader positions: {e}") from e

    async def store_trader_score(self, score: TraderScore) -> bool:
        """Store a trader score snapshot.

        Args:
            score: Score to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_SCORES]
            normalized = score.model_dump()
            normalized["eth"] = str(normalized.get("eth", "")).lower()
            normalized["tags"] = self._normalize_tags(normalized.get("tags"))
            comparable = self._score_snapshot_payload(normalized)

            latest = await collection.find_one(
                {"eth": comparable["eth"]},
                {
                    "_id": 0,
                    "eth": 1,
                    "score": 1,
                    "tags": 1,
                    "acct_val": 1,
                    "all_roi": 1,
                    "month_roi": 1,
                    "week_roi": 1,
                },
                sort=[("t", -1)],
            )
            if latest and self._score_snapshot_payload(latest) == comparable:
                return True

            await collection.insert_one(normalized)
            return True
        except Exception as e:
            raise StorageError(f"Failed to store trader score: {e}") from e

    async def upsert_tracked_trader(self, trader: TrackedTrader) -> bool:
        """Upsert a tracked trader.

        Args:
            trader: Trader to upsert.

        Returns:
            True if upserted successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            await collection.update_one(
                {"eth": trader.eth},
                {"$set": trader.model_dump()},
                upsert=True,
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to upsert tracked trader: {e}") from e

    async def store_signal(self, signal: TradingSignal) -> bool:
        """Store a trading signal.

        Uses sync pymongo via asyncio.to_thread() to avoid blocking the event loop
        on remote Atlas writes.

        Args:
            signal: Signal to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            return await asyncio.to_thread(self._sync_store_signal, signal)
        except Exception as e:
            raise StorageError(f"Failed to store signal: {e}") from e

    def _sync_store_signal(self, signal: TradingSignal) -> bool:
        """Sync implementation of store_signal (runs in thread pool)."""
        collection = self._sync_db[CollectionName.SIGNALS]
        collection.insert_one(signal.model_dump())
        return True

    async def get_signals(
        self,
        symbol: str,
        start_time: datetime | None = None,
        recommendation: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get signals for a symbol.

        Args:
            symbol: Trading symbol.
            start_time: Optional start time filter.
            recommendation: Filter by recommendation (BUY, SELL, NEUTRAL).
            limit: Maximum results.

        Returns:
            List of signal dictionaries.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.SIGNALS]
            query: dict[str, Any] = {"symbol": symbol}

            if start_time:
                query["t"] = {"$gte": start_time}

            if recommendation:
                query["rec"] = recommendation

            cursor = collection.find(query).sort("t", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            signals = []
            for doc in docs:
                doc.pop("_id", None)
                signals.append(doc)
            return signals
        except Exception as e:
            raise StorageError(f"Failed to get signals: {e}") from e

    async def get_latest_signal(self, symbol: str) -> TradingSignal | None:
        """Get the latest signal for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Latest signal or None.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.SIGNALS]
            doc = await collection.find_one(
                {"symbol": symbol},
                sort=[("t", -1)],
            )
            if doc:
                doc.pop("_id", None)
                return TradingSignal.model_validate(doc)
            return None
        except Exception as e:
            raise StorageError(f"Failed to get latest signal: {e}") from e

    async def store_trader_signal(self, signal: TraderSignal) -> bool:
        """Store a trader signal.

        Args:
            signal: Signal to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_SIGNALS]
            await collection.insert_one(signal.model_dump())
            return True
        except Exception as e:
            raise StorageError(f"Failed to store trader signal: {e}") from e

    async def get_trader_signals(
        self,
        address: str,
        start_time: datetime,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get signals for a specific trader.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for signals.
            limit: Maximum results.

        Returns:
            List of signal dictionaries.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_SIGNALS]
            query: dict[str, Any] = {"eth": address, "t": {"$gte": start_time}}

            cursor = collection.find(query).sort("t", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            signals = []
            for doc in docs:
                doc.pop("_id", None)
                signals.append(doc)
            return signals
        except Exception as e:
            raise StorageError(f"Failed to get trader signals: {e}") from e

    # ============== Interface Implementation Methods ==============

    async def get_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
        limit: int = 100,
        include_performances: bool = False,
    ) -> list[dict[str, Any]]:
        """Get tracked traders with filtering.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only return active traders.
            limit: Maximum results.

        Returns:
            List of trader dictionaries.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            query: dict[str, Any] = {}
            projection = {
                "_id": 0,
                "eth": 1,
                "address": 1,
                "name": 1,
                "displayName": 1,
                "score": 1,
                "tags": 1,
                "acct_val": 1,
                "accountValue": 1,
                "active": 1,
            }
            if include_performances:
                projection["performances"] = 1

            if active_only:
                query["active"] = True
            if min_score > 0:
                query["score"] = {"$gte": min_score}
            if tag:
                query["tags"] = tag

            cursor = collection.find(query, projection).sort("score", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            traders = []
            for doc in docs:
                doc.pop("_id", None)
                traders.append(doc)
            return traders
        except Exception as e:
            raise StorageError(f"Failed to get tracked traders: {e}") from e

    async def count_tracked_traders(
        self,
        min_score: float = 0,
        tag: str | None = None,
        active_only: bool = True,
        include_exact_count: bool = True,
    ) -> int:
        """Count tracked traders.

        Args:
            min_score: Minimum score filter.
            tag: Filter by tag.
            active_only: Only count active traders.

        Returns:
            Number of matching traders.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            if not include_exact_count:
                return 0

            collection = self._db[CollectionName.TRACKED_TRADERS]
            query: dict[str, Any] = {}

            if active_only:
                query["active"] = True
            if min_score > 0:
                query["score"] = {"$gte": min_score}
            if tag:
                query["tags"] = tag

            return await collection.count_documents(query)
        except Exception as e:
            raise StorageError(f"Failed to count tracked traders: {e}") from e

    async def get_trader_by_address(self, address: str) -> dict[str, Any] | None:
        """Get a trader by address.

        Args:
            address: Trader Ethereum address.

        Returns:
            Trader dictionary or None if not found.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            doc = await collection.find_one({"eth": address})
            if doc:
                doc.pop("_id", None)
                return doc
            # Try alternate field name
            doc = await collection.find_one({"address": address})
            if doc:
                doc.pop("_id", None)
            return doc
        except Exception as e:
            raise StorageError(f"Failed to get trader by address: {e}") from e

    async def get_trader_current_state(self, address: str) -> dict[str, Any] | None:
        """Get a trader's current state including positions.

        Args:
            address: Trader Ethereum address.

        Returns:
            Current state dictionary with positions, or None.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_CURRENT_STATE]
            projection = {
                "_id": 0,
                "eth": 1,
                "ethAddress": 1,
                "symbol": 1,
                "positions": 1,
                "open_orders": 1,
                "updated_at": 1,
                "last_event_time": 1,
            }
            doc = await collection.find_one({"eth": address}, projection)
            if not doc:
                # Backward-compatible fallback for legacy field name.
                doc = await collection.find_one({"ethAddress": address}, projection)
            return doc
        except Exception as e:
            raise StorageError(f"Failed to get trader current state: {e}") from e

    async def get_trader_current_states(
        self,
        addresses: list[str],
        symbol: str | None = None,
        include_legacy_fallback: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Get current state snapshots for multiple traders."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        normalized_addresses = sorted({str(address).lower() for address in addresses if address})
        if not normalized_addresses:
            return {}

        try:
            collection = self._db[CollectionName.TRADER_CURRENT_STATE]
            query_base: dict[str, Any] = {}
            if symbol is not None:
                query_base["symbol"] = symbol

            projection = {
                "_id": 0,
                "eth": 1,
                "ethAddress": 1,
                "symbol": 1,
                "positions": 1,
                "open_orders": 1,
                "updated_at": 1,
                "last_event_time": 1,
            }

            primary_query = {
                **query_base,
                "eth": {"$in": normalized_addresses},
            }
            primary_limit = max(50, len(normalized_addresses) * 2)
            primary_cursor = collection.find(primary_query, projection).sort(
                [
                    ("updated_at", -1),
                    ("last_event_time", -1),
                ]
            )
            primary_docs = await primary_cursor.to_list(length=primary_limit)

            states_by_address: dict[str, dict[str, Any]] = {}
            for doc in primary_docs:
                key = str(doc.get("eth") or "").lower()
                if not key or key not in normalized_addresses or key in states_by_address:
                    continue
                states_by_address[key] = doc

            if include_legacy_fallback and len(states_by_address) < len(normalized_addresses):
                missing_addresses = [address for address in normalized_addresses if address not in states_by_address]
                if missing_addresses:
                    legacy_query = {
                        **query_base,
                        "ethAddress": {"$in": missing_addresses},
                    }
                    legacy_limit = max(50, len(missing_addresses) * 2)
                    legacy_cursor = collection.find(legacy_query, projection).sort(
                        [
                            ("updated_at", -1),
                            ("last_event_time", -1),
                        ]
                    )
                    legacy_docs = await legacy_cursor.to_list(length=legacy_limit)

                    for doc in legacy_docs:
                        key = str(doc.get("ethAddress") or doc.get("eth") or "").lower()
                        if not key or key not in missing_addresses or key in states_by_address:
                            continue
                        states_by_address[key] = doc

            return states_by_address
        except Exception as e:
            raise StorageError(f"Failed to get trader current states: {e}") from e

    async def store_leaderboard_snapshot(
        self,
        symbol: str,
        total_count: int,
        tracked_count: int,
        timestamp: datetime | None = None,
    ) -> bool:
        """Store a lightweight leaderboard snapshot."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            now = timestamp or datetime.now(UTC)
            collection = self._db[CollectionName.LEADERBOARD_HISTORY]
            await collection.insert_one(
                {
                    "t": now,
                    "symbol": symbol,
                    "traderCount": total_count,
                    "trackedCount": tracked_count,
                }
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to store leaderboard snapshot: {e}") from e

    async def upsert_tracked_trader_data(
        self,
        trader: dict[str, Any],
        updated_at: datetime | None = None,
    ) -> bool:
        """Upsert normalized tracked trader data."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            address = str(trader.get("eth", "")).lower()
            if not address:
                return False

            now = updated_at or datetime.now(UTC)
            collection = self._db[CollectionName.TRACKED_TRADERS]
            doc = {
                "eth": address,
                "name": trader.get("name"),
                "score": float(trader.get("score", 0)),
                "acct_val": float(trader.get("acct_val", 0)),
                "tags": self._normalize_tags(trader.get("tags")),
                "performances": self._normalize_mapping(trader.get("performances")),
                "active": bool(trader.get("active", True)),
            }

            existing = await collection.find_one(
                {"eth": address},
                {
                    "_id": 0,
                    "eth": 1,
                    "name": 1,
                    "score": 1,
                    "acct_val": 1,
                    "tags": 1,
                    "performances": 1,
                    "active": 1,
                },
            )
            if existing and all(existing.get(key) == value for key, value in doc.items()):
                return True

            doc["updated_at"] = now

            await collection.update_one(
                {"eth": address},
                {"$set": doc, "$setOnInsert": {"added_at": now}},
                upsert=True,
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to upsert tracked trader data: {e}") from e

    async def deactivate_unselected_traders(
        self,
        selected_addresses: list[str],
        updated_at: datetime | None = None,
    ) -> int:
        """Deactivate active traders not in the selected address set.

        Uses sync pymongo via asyncio.to_thread() to avoid blocking the
        event loop with slow MongoDB Atlas round-trips (30s+ timeouts).
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            now = updated_at or datetime.now(UTC)
            normalized = [a.lower() for a in selected_addresses if a]

            def _sync_deactivate() -> int:
                collection = self._sync_db[CollectionName.TRACKED_TRADERS]
                query: dict[str, Any] = {"active": True}
                if normalized:
                    query["eth"] = {"$nin": normalized}
                result = collection.update_many(
                    query,
                    {"$set": {"active": False, "updated_at": now}},
                )
                return int(result.modified_count)

            return await asyncio.to_thread(_sync_deactivate)
        except Exception as e:
            raise StorageError(f"Failed to deactivate unselected traders: {e}") from e

    async def get_active_trader_addresses(self, limit: int = 5000) -> list[str]:
        """Get active tracked trader addresses."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            cursor = collection.find({"active": True}, {"eth": 1, "_id": 0}).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [str(d.get("eth", "")).lower() for d in docs if d.get("eth")]
        except Exception as e:
            raise StorageError(f"Failed to get active trader addresses: {e}") from e

    async def upsert_trader_current_state(
        self,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
    ) -> bool:
        """Upsert latest trader current state snapshot."""
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            return await asyncio.to_thread(
                self._sync_upsert_trader_current_state,
                address, symbol, positions, open_orders,
                margin_summary, event_timestamp, source,
            )
        except Exception as e:
            raise StorageError(f"Failed to upsert trader current state: {e}") from e

    def _sync_upsert_trader_current_state(
        self,
        address: str,
        symbol: str,
        positions: list[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        margin_summary: dict[str, Any] | None,
        event_timestamp: datetime,
        source: str,
    ) -> bool:
        """Sync implementation of upsert_trader_current_state (runs in thread pool)."""
        now = datetime.now(UTC)
        collection = self._sync_db[CollectionName.TRADER_CURRENT_STATE]
        existing = collection.find_one(
            {
                "symbol": str(symbol or "").upper(),
                "$or": [
                    {"eth": address.lower()},
                    {"ethAddress": address.lower()},
                ],
            },
            {
                "eth": 1, "ethAddress": 1, "symbol": 1,
                "positions": 1, "open_orders": 1, "margin_summary": 1,
                "last_event_time": 1, "source": 1, "btc_trade_meta": 1,
            },
        )

        doc, closed_trade = self._current_state_payload(
            address=address,
            symbol=symbol,
            positions=positions,
            open_orders=open_orders,
            margin_summary=margin_summary,
            event_timestamp=event_timestamp,
            source=source,
            existing_state=existing,
        )

        if closed_trade:
            ct_collection = self._sync_db[CollectionName.TRADER_CLOSED_TRADES]
            # closed_trade is a dict (from build_trader_current_state_payload), not a model
            ct_doc = dict(closed_trade) if not hasattr(closed_trade, "model_dump") else closed_trade.model_dump()
            ct_doc["eth"] = str(ct_doc.get("eth", "")).lower()
            ct_collection.update_one(
                {"eth": ct_doc["eth"], "coin": ct_doc["coin"], "closed_time": ct_doc["closed_time"]},
                {"$setOnInsert": ct_doc},
                upsert=True,
            )

        existing_compare = dict(existing) if existing else None
        if existing_compare:
            existing_compare.pop("_id", None)
        if existing_compare and existing_compare == doc:
            return True

        doc["updated_at"] = now
        update_filter: dict[str, Any] = {"eth": doc["eth"], "symbol": doc["symbol"]}
        if existing and existing.get("_id") is not None:
            update_filter = {"_id": existing["_id"]}
        collection.update_one(
            update_filter,
            {"$set": doc},
            upsert=True,
        )
        return True

    # ------------------------------------------------------------------
    # Bulk upsert: batched trader current-state writes (Phase 2B)
    # ------------------------------------------------------------------

    async def bulk_upsert_trader_states(
        self,
        state_items: list[tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, datetime, str]],
    ) -> int:
        """Bulk upsert multiple trader current-state documents in one bulk_write call.

        Each item is a tuple of:
            (address, symbol, positions, open_orders, margin_summary, event_timestamp, source)

        Uses pymongo ``bulk_write`` with ``UpdateOne`` operations filtered on
        ``(eth, symbol)`` and upsert=True.  Closed-trade detection is performed
        per-item by reading existing state first (batched find), then emitting
        any closed trades as a secondary ``insert_many`` with ``ordered=False``.

        Returns the number of upserted/modified state documents.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        if not state_items:
            return 0

        try:
            return await asyncio.to_thread(
                self._sync_bulk_upsert_trader_states, state_items
            )
        except Exception as e:
            raise StorageError(f"Failed to bulk upsert trader states: {e}") from e

    def _sync_bulk_upsert_trader_states(
        self,
        state_items: list[tuple[str, str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None, datetime, str]],
    ) -> int:
        """Sync implementation of bulk_upsert_trader_states (runs in thread pool)."""
        from pymongo import UpdateOne as SyncUpdateOne

        now = datetime.now(UTC)
        state_collection = self._sync_db[CollectionName.TRADER_CURRENT_STATE]
        closed_trade_collection = self._sync_db[CollectionName.TRADER_CLOSED_TRADES]

        # 1. Batch-fetch existing states for all addresses in one round-trip.
        #    We group by (eth, symbol) pairs and query with $or.
        filter_conditions: list[dict[str, Any]] = []
        for address, symbol, *_ in state_items:
            filter_conditions.append(
                {
                    "symbol": str(symbol or "").upper(),
                    "$or": [
                        {"eth": address.lower()},
                        {"ethAddress": address.lower()},
                    ],
                }
            )

        existing_states: dict[tuple[str, str], dict[str, Any]] = {}
        if filter_conditions:
            projection = {
                "eth": 1, "ethAddress": 1, "symbol": 1,
                "positions": 1, "open_orders": 1, "margin_summary": 1,
                "last_event_time": 1, "source": 1, "btc_trade_meta": 1,
            }
            try:
                cursor = state_collection.find(
                    {"$or": filter_conditions}, projection
                )
                for doc in cursor:
                    key = (doc.get("eth", "").lower(), doc.get("symbol", "").upper())
                    existing_states[key] = doc
            except Exception as e:
                logger.warning("bulk_upsert_batch_find_failed", error=str(e))
                # Fall through — missing existing_states means fresh upsert

        # 2. Build UpdateOne operations and collect closed trades.
        update_ops: list[SyncUpdateOne] = []
        closed_trade_docs: list[dict[str, Any]] = []
        processed_count = 0

        for address, symbol, positions, open_orders, margin_summary, event_timestamp, source in state_items:
            key = (address.lower(), str(symbol or "").upper())
            existing = existing_states.get(key)

            doc, closed_trade = self._current_state_payload(
                address=address,
                symbol=symbol,
                positions=positions,
                open_orders=open_orders,
                margin_summary=margin_summary,
                event_timestamp=event_timestamp,
                source=source,
                existing_state=existing,
            )

            # Collect closed trades for batch insert
            if closed_trade:
                ct_doc = dict(closed_trade) if not hasattr(closed_trade, "model_dump") else closed_trade.model_dump()
                ct_doc["eth"] = str(ct_doc.get("eth", "")).lower()
                closed_trade_docs.append(ct_doc)

            # Skip unchanged state documents
            existing_compare = dict(existing) if existing else None
            if existing_compare:
                existing_compare.pop("_id", None)
            if existing_compare and existing_compare == doc:
                processed_count += 1
                continue

            doc["updated_at"] = now
            update_filter = {"eth": doc["eth"], "symbol": doc["symbol"]}
            if existing and existing.get("_id") is not None:
                update_filter = {"_id": existing["_id"]}

            update_ops.append(
                SyncUpdateOne(update_filter, {"$set": doc}, upsert=True)
            )
            processed_count += 1

        # 3. Execute bulk_write for state upserts
        if update_ops:
            try:
                result = state_collection.bulk_write(update_ops, ordered=False)
                logger.debug(
                    "bulk_upsert_states_result",
                    matched=result.matched_count,
                    modified=result.modified_count,
                    upserted=result.upserted_count,
                )
            except BulkWriteError as e:
                logger.warning(
                    "bulk_upsert_states_partial_failure",
                    error=str(e),
                    details=e.details,
                )

        # 4. Batch insert closed trades (best-effort, ordered=False)
        if closed_trade_docs:
            try:
                closed_trade_collection.insert_many(
                    closed_trade_docs, ordered=False
                )
            except BulkWriteError:
                # Duplicate closed trades are acceptable
                logger.debug("bulk_upsert_closed_trades_duplicates_skipped")

        return processed_count

    async def store_dead_letter(
        self,
        event: StandardEvent,
        reason: str,
        error_message: str,
    ) -> bool:
        """Store failed events in a dead-letter collection.

        Uses sync pymongo via asyncio.to_thread() to avoid blocking the event loop.
        """
        if self._sync_db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            return await asyncio.to_thread(
                self._sync_store_dead_letter, event, reason, error_message
            )
        except Exception as e:
            raise StorageError(f"Failed to store dead letter event: {e}") from e

    def _sync_store_dead_letter(
        self, event: StandardEvent, reason: str, error_message: str
    ) -> bool:
        """Sync implementation of store_dead_letter (runs in thread pool)."""
        self._sync_db["dead_letters"].insert_one(
            {
                "event_id": event.event_id,
                "event_type": str(event.event_type),
                "source": event.source,
                "timestamp": datetime.now(UTC),
                "reason": reason,
                "error": error_message,
                "event": event.model_dump(),
            }
        )
        return True

    async def get_trader_positions_history(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get position history for a trader.

        Args:
            address: Trader Ethereum address.
            start_time: Start time for history.
            limit: Maximum results.

        Returns:
            List of position dictionaries.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_POSITIONS]
            query: dict[str, Any] = {
                "eth": address,
                "t": {"$gte": start_time},
            }

            cursor = collection.find(query).sort("t", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            positions = []
            for doc in docs:
                doc.pop("_id", None)
                positions.append(doc)
            return positions
        except Exception as e:
            raise StorageError(f"Failed to get trader positions history: {e}") from e

    async def get_trader_closed_trades(
        self,
        address: str,
        start_time: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get closed trades for a trader."""
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_CLOSED_TRADES]
            query = {
                "eth": address.lower(),
                "t": {"$gte": start_time},
            }

            cursor = collection.find(query).sort("t", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            trades = []
            for doc in docs:
                doc.pop("_id", None)
                trades.append(doc)
            return trades
        except Exception as e:
            raise StorageError(f"Failed to get trader closed trades: {e}") from e

    async def get_current_signal(self, symbol: str) -> dict[str, Any] | None:
        """Get the current/latest signal for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Latest signal dictionary or None.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.SIGNALS]
            doc = await collection.find_one(
                {"symbol": symbol},
                sort=[("t", -1)],
            )
            if doc:
                doc.pop("_id", None)
            return doc
        except Exception as e:
            raise StorageError(f"Failed to get current signal: {e}") from e

    async def get_signal_stats(
        self,
        symbol: str,
        start_time: datetime,
    ) -> dict[str, Any]:
        """Get aggregated signal statistics.

        Args:
            symbol: Trading symbol.
            start_time: Start time for statistics.

        Returns:
            Statistics dictionary with counts and averages.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.SIGNALS]
            pipeline = [
                {
                    "$match": {
                        "t": {"$gte": start_time},
                        "symbol": symbol,
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "buy": {"$sum": {"$cond": [{"$eq": ["$rec", "BUY"]}, 1, 0]}},
                        "sell": {"$sum": {"$cond": [{"$eq": ["$rec", "SELL"]}, 1, 0]}},
                        "neutral": {"$sum": {"$cond": [{"$eq": ["$rec", "NEUTRAL"]}, 1, 0]}},
                        "avg_confidence": {"$avg": "$conf"},
                        "avg_long_bias": {"$avg": "$long_bias"},
                    }
                },
            ]

            result = await collection.aggregate(pipeline).to_list(length=1)

            if result:
                stats = result[0]
                return {
                    "total": stats.get("total", 0),
                    "buy": stats.get("buy", 0),
                    "sell": stats.get("sell", 0),
                    "neutral": stats.get("neutral", 0),
                    "avg_confidence": round(stats.get("avg_confidence", 0) or 0, 4),
                    "avg_long_bias": round(stats.get("avg_long_bias", 0) or 0, 4),
                }

            return {
                "total": 0,
                "buy": 0,
                "sell": 0,
                "neutral": 0,
                "avg_confidence": 0.0,
                "avg_long_bias": 0.0,
            }
        except Exception as e:
            raise StorageError(f"Failed to get signal stats: {e}") from e

    async def get_signal_by_id(self, signal_id: str) -> dict[str, Any] | None:
        """Get a signal by its ID.

        Args:
            signal_id: Signal ObjectId as string.

        Returns:
            Signal dictionary or None if not found.

        Raises:
            StorageError: If not connected or query fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            from bson import ObjectId

            collection = self._db[CollectionName.SIGNALS]
            doc = await collection.find_one({"_id": ObjectId(signal_id)})
            if doc:
                doc["id"] = str(doc.pop("_id"))
            return doc
        except Exception as e:
            logger.debug("get_signal_by_id_error", signal_id=signal_id, error=str(e))
            return None

    async def track_trader(
        self,
        address: str,
        name: str | None = None,
        score: float = 0,
        tags: list[str] | None = None,
    ) -> bool:
        """Add or update a tracked trader.

        Args:
            address: Trader Ethereum address.
            name: Optional display name.
            score: Initial score.
            tags: Optional tags.

        Returns:
            True if successful.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        # Normalize address to lowercase to match unique index
        address = address.lower()

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            now = datetime.now(UTC)

            doc = {
                "eth": address,
                "active": True,
                "updated_at": now,
            }
            if name is not None:
                doc["name"] = name
            if score > 0:
                doc["score"] = score
            if tags is not None:
                doc["tags"] = tags

            await collection.update_one(
                {"eth": address},
                {"$set": doc, "$setOnInsert": {"added_at": now}},
                upsert=True,
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to track trader: {e}") from e

    async def untrack_trader(self, address: str) -> bool:
        """Mark a trader as inactive (soft delete).

        Args:
            address: Trader Ethereum address.

        Returns:
            True if successful.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRACKED_TRADERS]
            result = await collection.update_one(
                {"eth": address},
                {"$set": {"active": False, "updated_at": datetime.now(UTC)}},
            )
            return result.modified_count > 0 or result.matched_count > 0
        except Exception as e:
            raise StorageError(f"Failed to untrack trader: {e}") from e
