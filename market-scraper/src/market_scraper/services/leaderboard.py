"""Daily leaderboard fetch, score, filter, and store."""
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog

from market_scraper.config import get_settings
from market_scraper.db import get_db
from market_scraper.models import LeaderboardRow

logger = structlog.get_logger(__name__)

LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


class LeaderboardService:
    """Fetch Hyperliquid leaderboard daily, score traders, filter, and store."""

    def __init__(self):
        self.settings = get_settings()

    async def run_daily(self) -> int:
        """Run the daily fetch cycle. Returns count of tracked traders stored."""
        start = datetime.now(UTC)

        # 1. Fetch raw leaderboard (39K traders)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(LEADERBOARD_URL)
            resp.raise_for_status()
            rows_raw = resp.json().get("leaderboardRows", [])

        logger.info("leaderboard_fetched", raw_count=len(rows_raw))

        # 2. Score all traders
        scored: list[LeaderboardRow] = []
        for idx, row in enumerate(rows_raw):
            scored.append(self._score_trader(row, idx))

        logger.info("leaderboard_scored", count=len(scored))

        # 3. Hard filter: ALL required ROIs must be positive + min account value.
        # Note: Hyperliquid leaderboard only exposes day/week/month/allTime —
        # 'year' is omitted because it doesn't exist in the API response.
        filtered = [
            r for r in scored
            if r.roi_all_time > 0
            and r.roi_month > 0
            and r.acct_val >= self.settings.leaderboard.min_account_value
        ]

        # 4. Sort by score descending, take top N
        filtered.sort(key=lambda x: x.score, reverse=True)
        tracked = filtered[: self.settings.leaderboard.max_tracked]

        logger.info("leaderboard_filtered", filtered=len(filtered), tracked=len(tracked))

        # 5. Store to MongoDB
        db = get_db()
        today_str = date.today().isoformat()
        now = datetime.now(UTC)

        # Store full snapshot (top 10K for historical queries, TTL auto-expires)
        await db.leaderboard_daily.update_one(
            {"date": today_str},
            {"$set": {
                "date": today_str,
                "rows": [r.model_dump() for r in scored[:10000]],
                "total_fetched": len(rows_raw),
                "created_at": now,
            }},
            upsert=True,
        )

        # Replace tracked_traders entirely (daily refresh)
        await db.tracked_traders.delete_many({})
        await db.tracked_traders.insert_many([
            {
                "eth": t.eth,
                "name": t.name,
                "acct_val": t.acct_val,
                "score": t.score,
                "tags": t.tags,
                "leaderboard_rank": t.rank,
                "roi_all_time": t.roi_all_time,
                "roi_year": t.roi_year,
                "roi_month": t.roi_month,
                "roi_week": t.roi_week,
                "roi_day": t.roi_day,
                "volume_month": t.volume_month,
                "pnl_all_time": t.pnl_all_time,
                "selected_at": now,
                "last_position_update": None,
                "position_hash": None,
            }
            for t in tracked
        ])

        duration = (datetime.now(UTC) - start).total_seconds()
        logger.info(
            "leaderboard_daily_complete",
            fetched=len(rows_raw),
            scored=len(scored),
            filtered=len(filtered),
            tracked=len(tracked),
            duration_seconds=round(duration, 2),
        )
        return len(tracked)

    def _score_trader(self, row: dict[str, Any], rank: int) -> LeaderboardRow:
        """Score a single trader from leaderboard API response."""
        perfs = {}
        for p in row.get("windowPerformances", []):
            if len(p) >= 2:
                perfs[p[0]] = p[1]

        def get_roi(window: str) -> float:
            return float(perfs.get(window, {}).get("roi", 0) or 0)

        def get_volume(window: str) -> float:
            return float(perfs.get(window, {}).get("vlm", 0) or 0)

        acct_val = float(row.get("accountValue", 0) or 0)
        w = self.settings.leaderboard.weights

        score = 0.0
        # ROI scoring with multipliers
        score += min(get_roi("allTime") * 30, w.get("roi_all_time", 30))
        score += min(get_roi("month") * 50, w.get("roi_month", 25))
        score += max(min(get_roi("week") * 100, w.get("roi_week", 20)), -10)

        # Account value tier scoring
        if acct_val >= 10_000_000:
            score += w.get("account_value", 15) * 1.0
        elif acct_val >= 1_000_000:
            score += w.get("account_value", 15) * 0.8
        elif acct_val >= 100_000:
            score += w.get("account_value", 15) * 0.5
        elif acct_val >= 10_000:
            score += w.get("account_value", 15) * 0.3

        # Volume tier scoring
        month_vol = get_volume("month")
        vol_w = w.get("volume_month", 10)
        if month_vol >= 100_000_000:
            score += vol_w * 1.0
        elif month_vol >= 10_000_000:
            score += vol_w * 0.7
        elif month_vol >= 1_000_000:
            score += vol_w * 0.4

        # Tags
        tags = []
        if acct_val >= 10_000_000:
            tags.append("whale")
        elif acct_val >= 1_000_000:
            tags.append("large")
        elif acct_val >= 100_000:
            tags.append("mid")
        if get_roi("day") > 0 and get_roi("week") > 0 and get_roi("month") > 0:
            tags.append("consistent")
        if get_roi("allTime") > 1.0:
            tags.append("high_performer")

        # Elite requires score > 80 (use the score before rounding for accuracy)
        final_score = round(score, 2)
        if final_score > 80:
            tags.append("elite")

        return LeaderboardRow(
            eth=row.get("ethAddress", "").lower(),
            name=row.get("displayName"),
            acct_val=acct_val,
            roi_all_time=get_roi("allTime"),
            roi_year=float(perfs.get("year", {}).get("roi", 0) or 0),
            roi_month=get_roi("month"),
            roi_week=get_roi("week"),
            roi_day=get_roi("day"),
            volume_month=get_volume("month"),
            pnl_all_time=float(perfs.get("allTime", {}).get("pnl", 0) or 0),
            score=round(score, 2),
            tags=tags,
            rank=rank + 1,
        )


async def run_leaderboard_daily() -> int:
    """Standalone entry point for cron."""
    service = LeaderboardService()
    return await service.run_daily()
