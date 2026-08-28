"""BTC candle ingestion — fetch from Kraken and upsert to Mongo."""
import asyncio
from datetime import UTC, datetime

import structlog

from market_scraper.config import get_settings
from market_scraper.db import get_db
from market_scraper.services.candles import fetch_kraken_candles

logger = structlog.get_logger(__name__)

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]


async def ingest_interval(interval: str, limit: int = 100) -> int:
    """Fetch candles for one interval and upsert to btc_candles_{interval}."""
    candles = await fetch_kraken_candles(interval=interval, limit=limit)
    if not candles:
        logger.warning("candle_ingest_empty", interval=interval)
        return 0
    db = get_db()
    col = db[f"btc_candles_{interval}"]
    # Ensure index on t (non-unique, handle existing unique conflict)
    try:
        await col.create_index("t")
    except Exception:
        pass
    upserted = 0
    for c in candles:
        # Use t as unique key
        doc = {
            "t": c["t"],
            "open": c["open"],
            "high": c["high"],
            "low": c["low"],
            "close": c["close"],
            "volume": c["volume"],
            "interval": interval,
            "source": c.get("source", "kraken"),
        }
        try:
            res = await col.update_one({"t": c["t"]}, {"$set": doc}, upsert=True)
            if res.upserted_id is not None or res.modified_count > 0:
                upserted += 1
        except Exception as e:
            logger.warning("candle_upsert_failed", interval=interval, error=str(e))
    logger.info("candle_ingest_done", interval=interval, fetched=len(candles), upserted=upserted)
    return upserted


async def ingest_all(limit: int = 100) -> dict[str, int]:
    """Ingest all intervals. Returns dict interval->count."""
    results: dict[str, int] = {}
    for interval in INTERVALS:
        try:
            n = await ingest_interval(interval, limit=limit)
            results[interval] = n
        except Exception as e:
            logger.error("candle_ingest_error", interval=interval, error=str(e))
            results[interval] = 0
        # Small delay to respect Kraken rate limit (1 req per ~1s is safe)
        await asyncio.sleep(1)
    return results
