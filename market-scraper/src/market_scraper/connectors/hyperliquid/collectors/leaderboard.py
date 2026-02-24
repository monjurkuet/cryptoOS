# src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py

"""Leaderboard collector for periodic leaderboard fetching.

Fetches leaderboard from Hyperliquid Stats Data API, scores traders using
configurable weights, applies configurable filters, and stores derived data
to MongoDB.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog

from market_scraper.config.market_config import MarketConfig, load_market_config
from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.utils.hyperliquid import parse_window_performances

logger = structlog.get_logger(__name__)


class LeaderboardCollector:
    """Collects leaderboard data from Hyperliquid Stats Data API.

    Fetches leaderboard periodically, scores traders using configurable
    weights, applies configurable filters, and stores derived data to MongoDB.

    Features:
    - Configurable scoring weights via YAML
    - Configurable filter criteria (min_score, max_count, etc.)
    - Configurable tag thresholds
    - Direct database storage (bypasses event bus for large data)
    - Lightweight event emission for monitoring
    """

    # Use the stats-data endpoint for leaderboard (GET request, not POST)
    STATS_DATA_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
        db: Any = None,
        market_config: MarketConfig | None = None,
        refresh_interval: int | None = None,
    ) -> None:
        """Initialize the leaderboard collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
            db: Optional MongoDB database instance for direct storage
            market_config: Market configuration (loaded from YAML if not provided)
            refresh_interval: Seconds between refreshes (uses config if not provided)
        """
        self.event_bus = event_bus
        self.config = config
        self._db = db

        # Load market configuration
        self._market_config = market_config or load_market_config()

        # Use config refresh interval if not specified
        self._refresh_interval = refresh_interval or self._market_config.storage.refresh_interval

        self._running = False
        self._session: aiohttp.ClientSession | None = None
        self._refresh_task: asyncio.Task | None = None

        # Cached data
        self._last_fetch: datetime | None = None
        self._last_leaderboard: dict[str, Any] | None = None
        self._last_tracked_count: int = 0

        # Stats
        self._fetches = 0
        self._errors = 0

    async def start(self) -> None:
        """Start the collector.

        Non-blocking: Creates session and starts background tasks immediately.
        Initial fetch happens in background.
        """
        if self._running:
            return

        self._running = True
        self._session = aiohttp.ClientSession()

        # Start periodic refresh (includes initial fetch)
        self._refresh_task = asyncio.create_task(self._refresh_loop_with_initial())

        logger.info(
            "leaderboard_collector_started",
            refresh_interval=self._refresh_interval,
            min_score=self._market_config.filters.min_score,
            max_count=self._market_config.filters.max_count,
        )

    async def _refresh_loop_with_initial(self) -> None:
        """Refresh loop with initial fetch."""
        # Initial fetch
        await self._fetch_and_process()

        # Then periodic refresh
        await self._refresh_loop()

    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("leaderboard_refresh_task_cancelled")

        if self._session:
            await self._session.close()

        logger.info("leaderboard_collector_stopped", stats=self.get_stats())

    async def _refresh_loop(self) -> None:
        """Periodic refresh loop."""
        while self._running:
            await asyncio.sleep(self._refresh_interval)
            if self._running:
                await self._fetch_and_process()

    async def _fetch_and_process(self) -> None:
        """Fetch leaderboard, process with config, and store."""
        if not self._session:
            return

        try:
            # Fetch leaderboard
            leaderboard = await self._fetch_leaderboard()

            if leaderboard:
                self._last_leaderboard = leaderboard
                self._last_fetch = datetime.now(UTC)
                self._fetches += 1

                rows = leaderboard.get("leaderboardRows", [])
                total_traders = len(rows)

                # Score traders with configurable weights
                scored = self._score_traders(rows)

                # Apply configurable filters
                filtered = self._apply_filters(scored)

                self._last_tracked_count = len(filtered)

                # Store to database if available
                if self._db is not None:
                    await self._store_derived_data(filtered, total_traders)

                # Emit lightweight event (not full traders list - too large)
                event = StandardEvent.create(
                    event_type="leaderboard_processed",
                    source="hyperliquid_leaderboard",
                    payload={
                        "symbol": self.config.symbol,
                        "total_traders": total_traders,
                        "tracked_count": len(filtered),
                        "fetch_time": self._last_fetch.isoformat(),
                        "min_score": self._market_config.filters.min_score,
                        "max_count": self._market_config.filters.max_count,
                    },
                )

                await self.event_bus.publish(event)

                logger.info(
                    "leaderboard_processed",
                    total_traders=total_traders,
                    tracked_count=len(filtered),
                    min_score=self._market_config.filters.min_score,
                )

        except Exception as e:
            self._errors += 1
            logger.error("leaderboard_process_error", error=str(e), exc_info=True)

    def _score_traders(self, rows: list[dict]) -> list[dict]:
        """Score traders using configurable weights.

        Args:
            rows: Raw leaderboard rows

        Returns:
            List of scored traders sorted by score descending
        """
        scored = []

        for trader in rows:
            score = self._calculate_score(trader)
            tags = self._generate_tags(trader, score)

            # Parse performances
            performances = self._parse_performances(trader.get("windowPerformances", []))

            scored.append(
                {
                    "eth": trader.get("ethAddress", ""),
                    "name": trader.get("displayName"),
                    "score": score,
                    "acct_val": float(trader.get("accountValue", 0)),
                    "tags": tags,
                    "performances": performances,
                }
            )

        # Sort by score descending
        return sorted(scored, key=lambda x: x["score"], reverse=True)

    def _calculate_score(self, trader: dict) -> float:
        """Calculate score using configurable weights.

        Args:
            trader: Trader data dictionary

        Returns:
            Calculated score (0-100+)
        """
        config = self._market_config
        weights = config.scoring.weights
        score = 0.0

        # Parse performances
        performances = trader.get("windowPerformances", [])
        perfs = {}
        for p in performances:
            if len(p) >= 2:
                perfs[p[0]] = p[1]

        # All-time ROI (configurable weight)
        all_time_roi = float(perfs.get("allTime", {}).get("roi", 0) or 0)
        score += min(
            all_time_roi * config.scoring.roi_multipliers.get("all_time", 30), weights.all_time_roi
        )

        # Month ROI (configurable weight)
        month_roi = float(perfs.get("month", {}).get("roi", 0) or 0)
        score += min(month_roi * config.scoring.roi_multipliers.get("month", 50), weights.month_roi)

        # Week ROI (configurable weight, can be negative)
        week_roi = float(perfs.get("week", {}).get("roi", 0) or 0)
        week_score = week_roi * config.scoring.roi_multipliers.get("week", 100)
        score += max(min(week_score, weights.week_roi), -10)

        # Account value (tier-based)
        account_value = float(trader.get("accountValue", 0))
        for tier in config.account_value_tiers:
            if account_value >= tier.threshold:
                score += tier.points * (weights.account_value / 15)  # Normalize
                break

        # Volume (tier-based)
        month_volume = float(perfs.get("month", {}).get("vlm", 0) or 0)
        for tier in config.volume_tiers:
            if month_volume >= tier.threshold:
                score += tier.points * (weights.volume / 10)  # Normalize
                break

        # Consistency bonus (all timeframes positive)
        day_roi = float(perfs.get("day", {}).get("roi", 0) or 0)
        if day_roi > 0 and week_roi > 0 and month_roi > 0:
            score += config.scoring.consistency_bonus

        return round(score, 2)

    def _generate_tags(self, trader: dict, score: float) -> list[str]:
        """Generate tags for a trader based on configurable thresholds.

        Args:
            trader: Trader data dictionary
            score: Calculated score

        Returns:
            List of applicable tags
        """
        tags = []
        tag_config = self._market_config.tags

        account_value = float(trader.get("accountValue", 0))
        performances = self._parse_performances(trader.get("windowPerformances", []))

        # Whale tag
        if account_value >= tag_config.whale.get("threshold", 10_000_000):
            tags.append("whale")
        # Large tag
        elif account_value >= tag_config.large.get("threshold", 1_000_000):
            tags.append("large")

        # Top performer tag
        if score >= tag_config.top_performer.get("min_score", 80):
            tags.append("top_performer")

        # Elite tag
        if score >= tag_config.elite.get("min_score", 90):
            tags.append("elite")

        # Consistent tag
        required_positive = tag_config.consistent.get("require_positive", ["day", "week", "month"])
        if all(performances.get(t, {}).get("roi", 0) > 0 for t in required_positive):
            tags.append("consistent")

        # High performer tag
        all_time_roi = performances.get("allTime", {}).get("roi", 0)
        if all_time_roi >= tag_config.high_performer.get("all_time_roi", 1.0):
            tags.append("high_performer")

        # Volume tags
        month_volume = performances.get("month", {}).get("vlm", 0)
        if month_volume >= tag_config.high_volume.get("monthly_volume", 100_000_000):
            tags.append("high_volume")
        elif month_volume >= tag_config.medium_volume.get("monthly_volume", 10_000_000):
            tags.append("medium_volume")

        return tags

    def _parse_performances(self, performances: list) -> dict:
        """Parse window performances from list format.

        Uses shared utility function for consistency across codebase.

        Args:
            performances: List of [window, metrics] pairs

        Returns:
            Dict mapping window names to metrics
        """
        return parse_window_performances(performances)

    def _apply_filters(self, scored: list[dict]) -> list[dict]:
        """Apply configurable filters to scored traders.

        Args:
            scored: List of scored traders

        Returns:
            Filtered list of traders
        """
        filters = self._market_config.filters

        # Filter by min_score
        filtered = [t for t in scored if t["score"] >= filters.min_score]

        # Filter by min_account_value
        filtered = [t for t in filtered if t["acct_val"] >= filters.min_account_value]

        # Apply require_positive filters
        require_positive = filters.require_positive
        if require_positive:
            for timeframe, required in require_positive.items():
                if required:
                    filtered = [
                        t
                        for t in filtered
                        if t.get("performances", {}).get(timeframe, {}).get("roi", 0) > 0
                    ]

        # Apply exclude list
        exclude_addresses = set(filters.exclude.get("addresses", []))
        exclude_tags = set(filters.exclude.get("tags", []))
        if exclude_addresses:
            filtered = [t for t in filtered if t["eth"] not in exclude_addresses]
        if exclude_tags:
            filtered = [
                t for t in filtered if not any(tag in exclude_tags for tag in t.get("tags", []))
            ]

        # Limit to max_count
        return filtered[: filters.max_count]

    async def _store_derived_data(
        self,
        traders: list[dict],
        total_count: int,
    ) -> None:
        """Store derived leaderboard data to MongoDB.

        Stores:
        1. Lightweight snapshot to leaderboard_history
        2. Upsert traders to tracked_traders

        Args:
            traders: Filtered list of traders to track
            total_count: Total number of traders in leaderboard
        """
        if self._db is None:
            return

        try:
            from market_scraper.storage.models import CollectionName

            now = datetime.now(UTC)

            # 1. Store lightweight snapshot
            if self._market_config.storage.keep_snapshots:
                snapshot = {
                    "t": now,
                    "symbol": self.config.symbol,
                    "traderCount": total_count,
                    "trackedCount": len(traders),
                }
                await self._db[CollectionName.LEADERBOARD_HISTORY].insert_one(snapshot)

            # 2. Upsert traders
            selected_addresses = {t["eth"] for t in traders}

            for trader in traders:
                doc = {
                    "eth": trader["eth"],
                    "name": trader["name"],
                    "score": trader["score"],
                    "acct_val": trader["acct_val"],
                    "tags": trader["tags"],
                    "performances": trader.get("performances", {}),
                    "active": True,
                    "updated_at": now,
                }

                await self._db[CollectionName.TRACKED_TRADERS].update_one(
                    {"eth": trader["eth"]},
                    {"$set": doc, "$setOnInsert": {"added_at": now}},
                    upsert=True,
                )

            # 3. Deactivate traders not in selection
            if selected_addresses:
                await self._db[CollectionName.TRACKED_TRADERS].update_many(
                    {"eth": {"$nin": list(selected_addresses)}, "active": True},
                    {"$set": {"active": False, "updated_at": now}},
                )

            logger.info(
                "leaderboard_data_stored",
                tracked=len(traders),
                total=total_count,
            )

        except Exception as e:
            logger.error("leaderboard_storage_error", error=str(e), exc_info=True)

    async def _fetch_leaderboard(self) -> dict[str, Any] | None:
        """Fetch leaderboard from Stats Data API.

        Uses GET request to stats-data.hyperliquid.xyz endpoint.

        Returns:
            Leaderboard data or None on error
        """
        if not self._session:
            return None

        try:
            # Use longer timeout since leaderboard is large (~25MB)
            timeout = aiohttp.ClientTimeout(total=120)
            async with self._session.get(
                self.STATS_DATA_URL,
                timeout=timeout,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(
                        "leaderboard_api_error",
                        status=response.status,
                    )
                    return None

        except aiohttp.ClientError as e:
            logger.error("leaderboard_client_error", error=str(e), exc_info=True)
            return None
        except TimeoutError:
            logger.error("leaderboard_timeout")
            return None

    async def fetch_now(self) -> dict[str, Any] | None:
        """Force immediate fetch.

        Returns:
            Leaderboard data
        """
        await self._fetch_and_process()
        return self._last_leaderboard

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics.

        Returns:
            Stats dictionary
        """
        return {
            "running": self._running,
            "fetches": self._fetches,
            "errors": self._errors,
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "total_traders": len(self._last_leaderboard.get("leaderboardRows", []))
            if self._last_leaderboard
            else 0,
            "tracked_traders": self._last_tracked_count,
            "config": {
                "min_score": self._market_config.filters.min_score,
                "max_count": self._market_config.filters.max_count,
                "min_account_value": self._market_config.filters.min_account_value,
            },
        }

    @property
    def last_leaderboard(self) -> dict[str, Any] | None:
        """Get last fetched leaderboard."""
        return self._last_leaderboard

    @property
    def last_fetch_time(self) -> datetime | None:
        """Get last fetch time."""
        return self._last_fetch

    @property
    def market_config(self) -> MarketConfig:
        """Get the trader configuration."""
        return self._market_config

    async def get_tracked_addresses(self) -> list[str]:
        """Get list of tracked trader addresses from database.

        Returns tracked traders that are marked as active in the database.
        Falls back to empty list if database is not available.

        Returns:
            List of Ethereum addresses for tracked traders
        """
        if self._db is None:
            logger.warning("get_tracked_addresses_no_database")
            return []

        try:
            from market_scraper.storage.models import CollectionName

            cursor = self._db[CollectionName.TRACKED_TRADERS].find(
                {"active": True}, {"eth": 1, "_id": 0}
            )
            addresses = [doc["eth"] async for doc in cursor]
            logger.debug("get_tracked_addresses_found", count=len(addresses))
            return addresses
        except Exception as e:
            logger.error("get_tracked_addresses_error", error=str(e), exc_info=True)
            return []
