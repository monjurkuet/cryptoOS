"""Candle backfill service for historical data retrieval."""

import asyncio
from datetime import UTC, date, datetime, timedelta

import structlog

from market_scraper.config.market_config import CandleBackfillConfig
from market_scraper.connectors.hyperliquid.client import HyperliquidClient
from market_scraper.storage.base import DataRepository
from market_scraper.storage.models import Candle

logger = structlog.get_logger(__name__)


class CandleBackfillService:
    """Service for backfilling historical candle data.

    Fetches historical candles from Hyperliquid HTTP API and stores them
    in MongoDB. Supports all standard timeframes with configurable date range.
    """

    TIMEFRAME_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    # Hyperliquid launch date (earliest available data)
    HYPERLIQUID_EARLIEST = date(2023, 3, 1)

    def __init__(
        self,
        client: HyperliquidClient,
        repository: DataRepository,
        config: CandleBackfillConfig,
        symbol: str,
    ) -> None:
        self._client = client
        self._repository = repository
        self._config = config
        self._symbol = symbol

    async def run_backfill(self) -> dict[str, int]:
        """Run the complete backfill process.

        If incremental mode is enabled, checks for existing data and only
        fetches missing candles. This makes restarts much faster.

        Returns:
            Dictionary with candle counts per timeframe.
        """
        if not self._config.enabled:
            logger.info("backfill_disabled")
            return {}

        end_date = date.today()
        end_dt = datetime.combine(end_date, datetime.max.time())

        logger.info(
            "backfill_starting",
            symbol=self._symbol,
            timeframes=self._config.timeframes,
            incremental=self._config.incremental,
        )

        results = {}
        for timeframe in self._config.timeframes:
            try:
                # Determine start time based on incremental mode
                start_dt = await self._get_start_time(timeframe)
                count = await self._backfill_timeframe(timeframe, start_dt, end_dt)
                results[timeframe] = count
            except Exception as e:
                logger.error(
                    "backfill_timeframe_failed",
                    timeframe=timeframe,
                    error=str(e),
                    exc_info=True,
                )
                results[timeframe] = 0

        total = sum(results.values())
        logger.info("backfill_complete", total_candles=total, results=results)
        return results

    async def _get_start_time(self, timeframe: str) -> datetime:
        """Get start time for backfill.

        If incremental mode is enabled, returns the timestamp of the latest
        candle + 1 interval. Otherwise, returns the configured start_date or
        Hyperliquid's earliest date.

        Args:
            timeframe: Candle interval

        Returns:
            datetime to start fetching from
        """
        # Check for existing data if incremental mode
        if self._config.incremental:
            try:
                latest = await self._repository.get_latest_candle(
                    symbol=self._symbol,
                    interval=timeframe,
                )
                if latest and "t" in latest:
                    # Start from latest candle + 1 interval
                    interval_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 3600)
                    latest_time = latest["t"]
                    if isinstance(latest_time, str):
                        latest_time = datetime.fromisoformat(latest_time.replace("Z", "+00:00"))
                    start_dt = latest_time + timedelta(seconds=interval_seconds)
                    logger.info(
                        "backfill_incremental_start",
                        timeframe=timeframe,
                        latest_candle=latest_time.isoformat(),
                        starting_from=start_dt.isoformat(),
                    )
                    return start_dt
            except Exception as e:
                logger.warning("backfill_latest_check_failed", timeframe=timeframe, error=str(e))

        # No existing data or not incremental - use configured start date
        start_date = self._config.start_date or self.HYPERLIQUID_EARLIEST
        return datetime.combine(start_date, datetime.min.time())

    async def _backfill_timeframe(
        self,
        timeframe: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Backfill a single timeframe."""
        interval_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 60)
        batch_size = self._config.batch_size
        delay = self._config.rate_limit_delay

        # Calculate batch duration
        batch_duration_ms = interval_seconds * 1000 * batch_size

        total_stored = 0
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        while current_start < end_ms:
            current_end = min(current_start + batch_duration_ms, end_ms)

            try:
                candles_data = await self._client.get_candles(
                    coin=self._symbol,
                    interval=timeframe,
                    start_time=current_start,
                    end_time=current_end,
                )

                if candles_data:
                    candles = self._parse_candles(candles_data)
                    stored = await self._repository.store_candles_bulk(
                        candles=candles,
                        symbol=self._symbol,
                        interval=timeframe,
                    )
                    total_stored += stored

                await asyncio.sleep(delay)

            except Exception as e:
                logger.warning("backfill_batch_error", timeframe=timeframe, error=str(e))

            current_start = current_end

        logger.info("backfill_timeframe_complete", timeframe=timeframe, total=total_stored)
        return total_stored

    def _parse_candles(self, candles_data: list[dict]) -> list[Candle]:
        """Parse raw API response into Candle models."""
        candles = []
        for candle in candles_data:
            try:
                timestamp = candle.get("t") or candle.get("time")
                if timestamp:
                    if isinstance(timestamp, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp / 1000, UTC)
                    elif isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    else:
                        continue

                candles.append(
                    Candle(
                        t=timestamp,
                        o=float(candle.get("o") or candle.get("open", 0)),
                        h=float(candle.get("h") or candle.get("high", 0)),
                        l=float(candle.get("l") or candle.get("low", 0)),
                        c=float(candle.get("c") or candle.get("close", 0)),
                        v=float(candle.get("v") or candle.get("vol") or candle.get("volume", 0)),
                    )
                )
            except Exception as e:
                logger.warning("backfill_parse_error", error=str(e))

        return candles
