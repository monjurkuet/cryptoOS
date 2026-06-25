#!/usr/bin/env python3
"""
Standalone promotion evaluation script.

Bypasses the market_scraper HTTP API entirely to avoid event-loop blocking.
Can run as a cron job or be called directly.

Usage:
    python scripts/run_promotions.py

Cron example (every 15 min):
    */15 * * * * /home/administrator/githubrepo/cryptoOS/.venv/bin/python \
        /home/administrator/githubrepo/cryptoOS/scripts/run_promotions.py \
        >> /home/administrator/githubrepo/cryptoOS/logs/promotion_cron.log 2>&1

Environment:
    MONGO__URL          — MongoDB Atlas connection string (from .env)
    HTTP_PROXY          — Optional HTTP proxy for Hyperliquid API calls
"""

import asyncio
import os
import sys
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = "/home/administrator/githubrepo/cryptoOS"
SCRIPTS_DIR = f"{BASE_DIR}/scripts"
LOG_DIR = f"{BASE_DIR}/logs"

sys.path.insert(0, f"{BASE_DIR}/market-scraper/src")


# ── Load .env ──────────────────────────────────────────────────────────────────
def _load_dotenv():
    env_path = f"{BASE_DIR}/.env"
    if not os.path.exists(env_path):
        return
    for line in open(env_path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

# ── Imports (after dotenv) ─────────────────────────────────────────────────────
import aiohttp
import structlog
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection

from market_scraper.config.market_config import MarketConfig, load_market_config

from market_scraper.utils.hyperliquid import parse_window_performances

logger = structlog.get_logger(__name__)


# ── Config ─────────────────────────────────────────────────────────────────────
# Patch MarketConfig defaults in-memory so the script doesn't depend on
# startup-time YAML/config — the promotion cron needs cadence ENABLED.
def _patch_cadence_defaults(cfg: MarketConfig) -> MarketConfig:
    cfg.tracking_cadence.enabled = True
    cfg.filters.tiered_enabled = True
    return cfg


# ── HTTP client with optional proxy ────────────────────────────────────────────
def _build_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(trust_env=True)


# ── Leaderboard fetch (same logic as LeaderboardCollector._fetch_leaderboard) ──
STATS_DATA_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


async def _fetch_leaderboard(session: aiohttp.ClientSession) -> dict | None:
    try:
        async with session.get(STATS_DATA_URL, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status != 200:
                logger.error("leaderboard_fetch_http_error", status=r.status)
                return None
            return await r.json()
    except Exception as e:
        logger.error("leaderboard_fetch_error", error=str(e))
        return None


def _build_trader_dict(row: dict) -> dict:
    perfs = parse_window_performances(row.get("windowPerformances", []))
    return {
        "eth": str(row.get("ethAddress", "")).lower(),
        "acct_val": row.get("acctVal", 0),
        "score": row.get("score", 0),
        "performances": perfs,
        "name": row.get("name"),
    }


def _assign_cadence_tier(
    trader: dict,
    cadence_cfg,
) -> tuple[str, int]:
    """Mirror LeaderboardCollector._assign_cadence_tier logic.

    Returns (tier_name, check_interval_seconds).
    """
    if not cadence_cfg.enabled:
        return ("all", cadence_cfg.check_interval_base)

    perfs = trader.get("performances", {})
    month_roi = perfs.get("month", {}).get("roi", 0) if perfs else 0
    acct_val = float(trader.get("acct_val", 0) or 0)
    score = float(trader.get("score", 0) or 0)

    # Sort by: fewest max_traders first, then tightest check_interval
    sorted_tiers = sorted(
        cadence_cfg.tiers.items(),
        key=lambda x: (-x[1].max_traders, x[1].check_interval_seconds),
    )

    for tier_name, tier_cfg in sorted_tiers:
        if (acct_val >= tier_cfg.min_acct_val
                and month_roi >= tier_cfg.min_month_roi
                and score >= tier_cfg.min_score):
            return (tier_name, tier_cfg.check_interval_seconds)

    return ("default", cadence_cfg.check_interval_base)


# ── Main ───────────────────────────────────────────────────────────────────────
async def main() -> int:
    start = datetime.utcnow()
    log = []

    def log_msg(msg: str):
        ts = datetime.utcnow().isoformat()
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        log.append(line)

    log_msg("=== Promotion Evaluation Started ===")

    # 1. Connect to MongoDB (sync pymongo — runs in background thread)
    mongo_url = os.environ.get("MONGO__URL", "")
    if not mongo_url:
        log_msg("ERROR: MONGO__URL not set in environment")
        return 1

    def _sync_connect():
        c = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
        c.admin.command("ping")
        return c

    try:
        loop = asyncio.get_event_loop()
        sync_client = await loop.run_in_executor(None, _sync_connect)
        db = sync_client.market_scraper
        tracked_coll: Collection = db.tracked_traders
        log_msg(f"MongoDB connected: {mongo_url.split('@')[1] if '@' in mongo_url else 'ok'}")
    except Exception as e:
        log_msg(f"ERROR: MongoDB connection failed: {e}")
        return 1

    # 2. Build config (patch cadence enabled)
    market_config: MarketConfig = load_market_config()
    market_config = _patch_cadence_defaults(market_config)
    cadence_cfg = market_config.tracking_cadence
    filters_cfg = market_config.filters

    log_msg(f"cadence_enabled={cadence_cfg.enabled}, tiered_enabled={filters_cfg.tiered_enabled}")

    # 3. Fetch leaderboard
    session = _build_session()
    try:
        log_msg("Fetching leaderboard from Hyperliquid...")
        leaderboard = await _fetch_leaderboard(session)
        if not leaderboard:
            log_msg("ERROR: Failed to fetch leaderboard")
            return 1
        rows = leaderboard.get("leaderboardRows", [])
        log_msg(f"Leaderboard rows: {len(rows)}")
    finally:
        await session.close()

    # 5. Build trader map
    trader_map: dict[str, dict] = {}
    for row in rows:
        addr = str(row.get("ethAddress", "")).lower()
        if not addr:
            continue
        perfs = parse_window_performances(row.get("windowPerformances", []))
        trader_map[addr] = {
            "eth": addr,
            "acct_val": row.get("acctVal", 0),
            "score": row.get("score", 0),
            "performances": perfs,
            "name": row.get("name"),
        }

    log_msg(f"Trader map size: {len(trader_map)}")

    # 6. Get tracked traders from MongoDB (sync pymongo via executor)
    def _fetch_tracked():
        return list(tracked_coll.find(
            {"active": True},
            {"eth": 1, "cadence_tier": 1, "acct_val": 1, "score": 1},
        ).limit(500))

    try:
        tracked = await loop.run_in_executor(None, _fetch_tracked)
        log_msg(f"Tracked traders in DB: {len(tracked)}")
    except Exception as e:
        log_msg(f"ERROR: get_tracked_traders failed: {e}")
        return 1

    # 7. Evaluate promotions
    promotions = 0
    demotions = 0
    unchanged = 0
    errors = 0
    tier_updates = []  # collected and batch-written after the loop

    for t in tracked:
        addr = str(t.get("eth", "")).lower()
        api_trader = trader_map.get(addr)
        if not api_trader:
            # Trader no longer on leaderboard
            unchanged += 1
            continue

        # Assign tier to api_trader and determine change
        tier_name, _ = _assign_cadence_tier(api_trader, cadence_cfg)
        api_trader["cadence_tier"] = tier_name

        old_tier = t.get("cadence_tier") or "unknown"
        new_tier = tier_name

        if new_tier != old_tier:
            action = "PROMOTE" if new_tier in ("gold", "silver") else "DEMOTE"
            log_msg(f"  {action}: {addr[:12]}... {old_tier} → {new_tier}")
            tier_updates.append((addr, new_tier))
            if new_tier in ("gold", "silver"):
                promotions += 1
            else:
                demotions += 1
        else:
            unchanged += 1

    # 8. Batch-write all tier changes in one bulk operation
    if tier_updates:
        def _bulk_write():
            ops = [UpdateOne({"eth": addr}, {"$set": {"cadence_tier": tier}})
                   for addr, tier in tier_updates]
            return tracked_coll.bulk_write(ops, ordered=False)

        result = await loop.run_in_executor(None, _bulk_write)
        log_msg(f"  Wrote {result.modified_count}/{len(tier_updates)} tier updates to DB")

    elapsed = (datetime.utcnow() - start).total_seconds()

    log_msg("=== Promotion Evaluation Complete ===")
    log_msg(f"  Evaluated : {len(tracked)}")
    log_msg(f"  Promotions: {promotions}")
    log_msg(f"  Demotions : {demotions}")
    log_msg(f"  Unchanged : {unchanged}")
    log_msg(f"  Errors    : {errors}")
    log_msg(f"  Elapsed   : {elapsed:.1f}s")

    # Write to log file
    log_path = f"{LOG_DIR}/promotion_cron.log"
    try:
        with open(log_path, "a") as f:
            f.write("\n".join(log) + "\n")
    except Exception:
        pass

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)