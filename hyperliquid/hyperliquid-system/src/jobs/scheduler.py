"""
Scheduler Module.

This module provides the APScheduler setup for all collection jobs.
"""

import asyncio
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.config import settings


def setup_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns:
        Configured AsyncIOScheduler
    """
    scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,  # Combine missed jobs
            "max_instances": 1,  # Only one instance of each job
            "misfire_grace_time": 60,  # Grace period for missed jobs
        },
    )

    logger.info("Scheduler configured")
    return scheduler


def add_jobs(
    scheduler: AsyncIOScheduler,
    db,
    hl_client,
    cf_client,
    stats_client,
    ws_available: bool = False,
) -> None:
    """
    Add all collection jobs to the scheduler.

    Args:
        scheduler: APScheduler instance
        db: MongoDB database
        hl_client: Hyperliquid API client
        cf_client: CloudFront API client
        stats_client: Stats Data API client
        ws_available: Whether WebSocket is available (use REST fallback if not)
    """
    from src.jobs.archive import archive_all_collections
    from src.jobs.btc_candles import collect_candles
    from src.jobs.btc_daily_stats import collect_daily_stats
    from src.jobs.btc_funding import collect_funding
    from src.jobs.btc_orderbook import collect_orderbook
    from src.jobs.btc_signals import generate_signals
    from src.jobs.btc_trades import collect_trades
    from src.jobs.btc_ticker import update_ticker
    from src.jobs.leaderboard import fetch_leaderboard, update_tracked_traders
    from src.jobs.trader_orders import collect_trader_orders
    # =========================================================================
    # High Frequency Jobs (Every 30 seconds)
    # =========================================================================

    # Only add REST jobs if WebSocket is NOT available
    # WebSocket collectors handle these in real-time
    if not ws_available:
        # Orderbook - REST fallback
        scheduler.add_job(
            collect_orderbook,
            trigger=IntervalTrigger(seconds=settings.orderbook_interval),
            args=[hl_client, db],
            id="collect_orderbook",
            name="Collect BTC Orderbook (REST)",
            replace_existing=True,
        )

        # Trades - REST fallback
        scheduler.add_job(
            collect_trades,
            trigger=IntervalTrigger(seconds=settings.trades_interval),
            args=[hl_client, db],
            id="collect_trades",
            name="Collect BTC Trades (REST)",
            replace_existing=True,
        )
    else:
        logger.info("WebSocket orderbook/trades active - skipping REST jobs")

    # Trader positions are now handled by PersistentTraderWebSocketManager
    # which runs continuously outside the scheduler
    logger.info("Trader positions handled by PersistentTraderWebSocketManager")

    scheduler.add_job(
        generate_signals,
        trigger=IntervalTrigger(seconds=settings.signals_interval),
        args=[db],
        id="generate_signals",
        name="Generate BTC Signals",
        replace_existing=True,
    )

    # =========================================================================
    # Medium Frequency Jobs (Every 1-5 minutes)
    # =========================================================================

    # Candles - skip if WebSocket is active (WS handles real-time candles)
    if not ws_available:
        scheduler.add_job(
            collect_candles,
            trigger=IntervalTrigger(seconds=settings.candles_interval),
            args=[hl_client, db],
            id="collect_candles",
            name="Collect BTC Candles (REST)",
            replace_existing=True,
        )
    else:
        logger.info("WebSocket candles active - skipping REST candles job")

    scheduler.add_job(
        update_ticker,
        trigger=IntervalTrigger(seconds=settings.ticker_interval),
        args=[hl_client, db],
        id="update_ticker",
        name="Update BTC Ticker",
        replace_existing=True,
    )

    # Trader orders - use WebSocket when available
    if ws_available:
        # WebSocket order collection handled by PersistentTraderOrdersWSManager
        logger.info("Trader orders handled by PersistentTraderOrdersWSManager")
    else:
        # Fallback to REST API
        scheduler.add_job(
            collect_trader_orders,
            trigger=IntervalTrigger(seconds=settings.trader_orders_interval),
            args=[hl_client, db],
            id="collect_trader_orders",
            name="Collect Trader Orders (REST)",
            replace_existing=True,
        )
        logger.info("Using REST for trader orders (fallback)")

    # =========================================================================
    # Low Frequency Jobs (Every 8 hours)
    # =========================================================================
    scheduler.add_job(
        collect_funding,
        trigger=IntervalTrigger(seconds=settings.funding_interval),
        args=[hl_client, db],
        id="collect_funding",
        name="Collect BTC Funding",
        replace_existing=True,
    )

    # =========================================================================
    # Daily Jobs
    # =========================================================================
    scheduler.add_job(
        fetch_leaderboard,
        trigger=IntervalTrigger(seconds=settings.trader_selection_interval),
        args=[stats_client, db],
        id="fetch_leaderboard",
        name="Fetch Leaderboard",
        replace_existing=True,
    )

    scheduler.add_job(
        update_tracked_traders,
        trigger=IntervalTrigger(seconds=settings.trader_selection_interval),
        args=[db, stats_client],
        id="update_tracked_traders",
        name="Update Tracked Traders",
        replace_existing=True,
    )

    scheduler.add_job(
        collect_daily_stats,
        trigger=IntervalTrigger(seconds=86400),  # Daily
        args=[cf_client, db],
        id="collect_daily_stats",
        name="Collect Daily Stats",
        replace_existing=True,
    )

    scheduler.add_job(
        archive_all_collections,
        trigger=IntervalTrigger(seconds=settings.archive_interval),
        args=[db],
        id="archive_collections",
        name="Archive Old Data",
        replace_existing=True,
    )

    logger.info(f"Added {len(scheduler.get_jobs())} jobs to scheduler")


async def run_startup_tasks(
    db,
    hl_client,
    cf_client,
    stats_client,
    ws_available: bool = False,
) -> None:
    """
    Run initial data collection tasks on startup.

    Args:
        db: MongoDB database
        hl_client: Hyperliquid API client
        cf_client: CloudFront API client
        stats_client: Stats Data API client
        ws_available: Whether WebSocket is available
    """
    from src.jobs.btc_candles import collect_candles
    from src.jobs.btc_ticker import update_ticker
    from src.jobs.leaderboard import fetch_leaderboard
    from src.jobs.trader_positions import collect_all_positions

    logger.info("Running startup tasks...")

    try:
        # Initial ticker update
        logger.info("Fetching initial ticker...")
        await update_ticker(hl_client, db)

        # Initial candles (last 24 hours for each interval)
        logger.info("Backfilling recent candles...")
        await collect_candles(hl_client, db)

        # Fetch leaderboard and set up tracked traders (updates traders directly)
        logger.info("Fetching initial leaderboard...")
        await fetch_leaderboard(stats_client, db)

        # Initial position collection is handled by PersistentTraderWebSocketManager
        logger.info("Trader positions will be collected by PersistentTraderWebSocketManager")

        logger.info("Startup tasks completed")

    except Exception as e:
        logger.error(f"Error during startup tasks: {e}")
        raise


def get_job_status(scheduler: AsyncIOScheduler) -> dict:
    """
    Get status of all scheduled jobs.

    Args:
        scheduler: APScheduler instance

    Returns:
        Dictionary with job status information
    """
    jobs = scheduler.get_jobs()

    return {
        "total_jobs": len(jobs),
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ],
    }
