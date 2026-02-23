"""MongoDB repository implementation for the Market Scraper Framework."""

from datetime import UTC, datetime
from typing import Any

import motor.motor_asyncio
import structlog

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import StorageError
from market_scraper.core.types import Symbol, Timeframe
from market_scraper.storage.base import DataRepository, QueryFilter
from market_scraper.storage.models import (
    Candle,
    CollectionName,
    Orderbook,
    TrackedTrader,
    Trade,
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
        self._client: motor.motor_asyncio.AsyncIOMotorClient | None = None
        self._db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None

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
            )
            self._db = self._client[self._database_name]
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
        if self._client:
            self._client.close()
            logger.info("mongodb_disconnected")
        self._connected = False
        self._client = None
        self._db = None

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
        """Create TTL indexes for automatic data retention."""
        if self._db is None:
            return

        retention = self._get_retention_config()

        # Global collections with TTL indexes
        ttl_collections = [
            ("events", "timestamp", retention.events),
            (CollectionName.LEADERBOARD_HISTORY, "t", retention.leaderboard_history),
            (CollectionName.TRADER_POSITIONS, "t", retention.trader_positions),
            (CollectionName.TRADER_SCORES, "t", retention.trader_scores),
            (CollectionName.SIGNALS, "t", retention.signals),
            (CollectionName.TRADER_SIGNALS, "t", retention.trader_signals),
            (CollectionName.MARK_PRICES, "t", retention.mark_prices),
        ]

        for collection_name, field, days in ttl_collections:
            try:
                await self._db[collection_name].create_index(
                    [(field, 1)],
                    name="ttl_retention",
                    expireAfterSeconds=days * 86400,
                )
                logger.info(
                    "ttl_index_created",
                    collection=collection_name,
                    retention_days=days,
                )
            except Exception as e:
                # Index might already exist with different options
                logger.warning(
                    "ttl_index_creation_failed",
                    collection=collection_name,
                    error=str(e),
                )

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
        except Exception:
            # Return default retention config
            from market_scraper.config.market_config import RetentionConfig

            return RetentionConfig()

    async def store(self, event: StandardEvent) -> bool:
        """Store a single event.

        Args:
            event: Event to store.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            await self._db.events.insert_one(event.model_dump())
            return True
        except Exception as e:
            raise StorageError(f"Failed to store event: {e}") from e

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
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        if not events:
            return 0

        try:
            documents = [e.model_dump() for e in events]
            result = await self._db.events.insert_many(
                documents,
                ordered=False,  # Continue on error
            )
            return len(result.inserted_ids)
        except Exception as e:
            # Check if it's a bulk write error with partial success
            if hasattr(e, "details") and e.details:
                n_inserted = e.details.get("nInserted", 0)
                if n_inserted > 0:
                    return n_inserted
            raise StorageError(f"Failed to store bulk events: {e}") from e

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
        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
        elif timeframe.endswith("h"):
            minutes = int(timeframe[:-1]) * 60
        elif timeframe.endswith("d"):
            minutes = int(timeframe[:-1]) * 60 * 24
        elif timeframe.endswith("w"):
            minutes = int(timeframe[:-1]) * 60 * 24 * 7
        elif timeframe == "1M":
            minutes = 30 * 60 * 24  # Approximate month
        elif timeframe.endswith("s"):
            minutes = int(timeframe[:-1]) / 60
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        interval_ms = int(minutes * 60 * 1000)

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
            except Exception:
                # Collection might not exist yet
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

    async def store_trade(self, trade: Trade, symbol: str) -> bool:
        """Store a trade.

        Args:
            trade: Trade to store.
            symbol: Trading symbol (e.g., "BTC").

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.trades(symbol)]
            await collection.update_one(
                {"tid": trade.tid},
                {"$setOnInsert": trade.model_dump()},
                upsert=True,
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to store trade: {e}") from e

    async def store_trades_bulk(self, trades: list[Trade], symbol: str) -> int:
        """Store multiple trades efficiently.

        Args:
            trades: List of trades to store.
            symbol: Trading symbol.

        Returns:
            Number of trades stored.

        Raises:
            StorageError: If not connected.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        if not trades:
            return 0

        try:
            collection = self._db[CollectionName.trades(symbol)]
            documents = [trade.model_dump() for trade in trades]
            result = await collection.insert_many(documents, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            if hasattr(e, "details") and e.details:
                n_inserted = e.details.get("nInserted", 0)
                if n_inserted > 0:
                    return n_inserted
            raise StorageError(f"Failed to store trades: {e}") from e

    async def store_orderbook(self, orderbook: Orderbook, symbol: str) -> bool:
        """Store an orderbook snapshot.

        Args:
            orderbook: Orderbook to store.
            symbol: Trading symbol.

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.orderbook(symbol)]
            await collection.insert_one(orderbook.model_dump())
            return True
        except Exception as e:
            raise StorageError(f"Failed to store orderbook: {e}") from e

    async def store_candle(self, candle: Candle, symbol: str, interval: str) -> bool:
        """Store a candle.

        Args:
            candle: Candle to store.
            symbol: Trading symbol.
            interval: Candle interval (e.g., "1m", "5m").

        Returns:
            True if stored successfully.

        Raises:
            StorageError: If not connected or storage fails.
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.candles(symbol, interval)]
            await collection.update_one(
                {"t": candle.t},
                {"$set": candle.model_dump()},
                upsert=True,
            )
            return True
        except Exception as e:
            raise StorageError(f"Failed to store candle: {e}") from e

    async def store_candles_bulk(
        self,
        candles: list[Candle],
        symbol: str,
        interval: str,
    ) -> int:
        """Store multiple candles efficiently using bulk write with upsert.

        Args:
            candles: List of candles to store
            symbol: Trading symbol (e.g., "BTC")
            interval: Candle interval (e.g., "1h")

        Returns:
            Number of candles inserted/modified

        Raises:
            StorageError: If not connected or storage fails
        """
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        if not candles:
            return 0

        try:
            from pymongo import UpdateOne

            collection = self._db[CollectionName.candles(symbol, interval)]
            operations = [
                UpdateOne(
                    {"t": candle.t},
                    {"$set": candle.model_dump()},
                    upsert=True,
                )
                for candle in candles
            ]
            result = await collection.bulk_write(operations, ordered=False)
            return result.upserted_count + result.modified_count
        except Exception as e:
            raise StorageError(f"Failed to store candles bulk: {e}") from e

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
        if self._db is None:
            raise StorageError("Not connected to MongoDB")

        try:
            collection = self._db[CollectionName.TRADER_POSITIONS]
            await collection.insert_one(position.model_dump())
            return True
        except Exception as e:
            raise StorageError(f"Failed to store position: {e}") from e

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
            await collection.insert_one(score.model_dump())
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
            collection = self._db[CollectionName.SIGNALS]
            await collection.insert_one(signal.model_dump())
            return True
        except Exception as e:
            raise StorageError(f"Failed to store signal: {e}") from e

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

            if active_only:
                query["active"] = True
            if min_score > 0:
                query["score"] = {"$gte": min_score}
            if tag:
                query["tags"] = tag

            cursor = collection.find(query).sort("score", -1).limit(limit)
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
            doc = await collection.find_one({"ethAddress": address})
            if doc:
                doc.pop("_id", None)
            return doc
        except Exception as e:
            raise StorageError(f"Failed to get trader current state: {e}") from e

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
