"""LED daily leaderboard fetch — cron entry point."""
import asyncio
import sys

import structlog

from market_scraper.config import get_settings
from market_scraper.db import close_mongo, connect_mongo
from market_scraper.services.leaderboard import LeaderboardService


def _configure_logging() -> None:
    settings = get_settings()
    import logging
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if settings.log_format == "json"
                else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def _run_daily() -> int:
    _configure_logging()
    settings = get_settings()
    await connect_mongo(settings.mongo_url, settings.mongo_db)
    try:
        service = LeaderboardService()
        count = await service.run_daily()
    finally:
        await close_mongo()
    return count


def main() -> int:
    count = asyncio.run(_run_daily())
    print(f"Daily leaderboard stored: {count} tracked traders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
