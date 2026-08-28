"""MongoDB connection and indexes."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_mongo(url: str, db_name: str) -> AsyncIOMotorDatabase:
    global _client, _db
    _client = AsyncIOMotorClient(
        url,
        maxPoolSize=10,
        minPoolSize=1,
        serverSelectionTimeoutMS=5000,
    )
    await _client.admin.command("ping")
    _db = _client[db_name]
    await _ensure_indexes(_db)
    return _db


async def close_mongo() -> None:
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected")
    return _db


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    from pymongo import ASCENDING, DESCENDING, IndexModel
    retention_days = 365
    position_days = 30

    await db.leaderboard_daily.create_indexes([
        IndexModel([("date", DESCENDING)]),
        IndexModel([("date", DESCENDING), ("score", DESCENDING)]),
        IndexModel(
            [("created_at", ASCENDING)],
            expireAfterSeconds=retention_days * 86400,
            name="ttl",
        ),
    ])

    await db.tracked_traders.create_indexes([
        IndexModel([("eth", ASCENDING)], unique=True),
        IndexModel([("score", DESCENDING)]),
        IndexModel([("roi_all_time", ASCENDING)]),
    ])

    await db.trader_positions.create_indexes([
        IndexModel([("eth", ASCENDING), ("t", DESCENDING)]),
        IndexModel(
            [("t", ASCENDING)],
            expireAfterSeconds=position_days * 86400,
            name="ttl",
        ),
    ])

    await db.trader_current_state.create_indexes([
        IndexModel([("eth", ASCENDING)], unique=True),
    ])

    for col in ["btc_candles_1m", "btc_candles_5m", "btc_candles_15m", "btc_candles_1h", "btc_candles_4h", "btc_candles_1d", "eth_candles_1h"]:
        try:
            await db[col].create_indexes([
                IndexModel([("t", ASCENDING)]),
                IndexModel([("t", DESCENDING)]),
            ])
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "indexkeyspecsconflict" in msg or "code': 86" in msg:
                try:
                    await db[col].drop_index("t_1")
                    await db[col].create_indexes([
                        IndexModel([("t", ASCENDING)]),
                        IndexModel([("t", DESCENDING)]),
                    ])
                except Exception:
                    pass
            elif "duplicate" not in msg:
                raise
