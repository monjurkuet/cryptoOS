#!/usr/bin/env python3
"""
Hyperliquid BTC Trading System - Main Entry Point.

This is the main entry point for the data collection and trader tracking system.
"""

import asyncio
import signal
import sys
from datetime import datetime

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from src.api.cloudfront import CloudFrontClient
from src.api.hyperliquid import HyperliquidClient
from src.api.stats_data import StatsDataClient
from src.api.websocket import WebSocketManager
from src.config import settings
from src.database import check_database_connection, setup_database
from src.jobs.btc_orderbook_ws import OrderbookWebSocketCollector
from src.jobs.btc_trades_ws import TradesWebSocketCollector
from src.jobs.btc_candles_ws import CandleWebSocketCollector
from src.jobs.btc_all_mids_ws import AllMidsWebSocketCollector
from src.api.persistent_trader_ws import PersistentTraderWebSocketManager
from src.api.persistent_trader_orders_ws import PersistentTraderOrdersWSManager
from src.jobs.scheduler import add_jobs, run_startup_tasks, setup_scheduler
from src.utils.helpers import utcnow


def configure_logging() -> None:
    """Configure loguru logging."""
    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
    )

    # Add file handler
    logger.add(
        settings.log_file,
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


async def main() -> None:
    """Main application entry point."""
    configure_logging()

    logger.info("=" * 60)
    logger.info("Hyperliquid BTC Trading System")
    logger.info("=" * 60)
    logger.info(f"Started at: {utcnow().isoformat()}")
    logger.info(f"Database: {settings.mongodb_db_name}")
    logger.info(f"Target coin: {settings.target_coin}")
    logger.info(f"Max tracked traders: {settings.max_tracked_traders}")
    logger.info(f"WebSocket enabled: {settings.websocket_enabled}")
    logger.info("=" * 60)

    # Initialize MongoDB client with connection pool settings
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        maxPoolSize=50,
        minPoolSize=10,
        maxIdleTimeMS=30000,
    )
    db = client[settings.mongodb_db_name]

    # Check database connection
    if not await check_database_connection(db):
        logger.error("Failed to connect to MongoDB. Exiting.")
        sys.exit(1)

    logger.info("MongoDB connection successful")

    # Setup database (collections and indexes)
    logger.info("Setting up database...")
    await setup_database(db)

    # Initialize API clients
    hl_client = HyperliquidClient()
    cf_client = CloudFrontClient()
    stats_client = StatsDataClient()

    # Enter async context for clients
    await hl_client.__aenter__()
    await cf_client.__aenter__()
    await stats_client.__aenter__()

    # Initialize WebSocket manager and collectors
    ws_manager = None
    orderbook_collector = None
    trades_collector = None
    candles_collector = None
    all_mids_collector = None
    scheduler = None
    trader_ws_manager = None
    trader_orders_ws_manager = None

    if settings.websocket_enabled:
        logger.info("Initializing WebSocket connections...")
        ws_manager = WebSocketManager()

        ws_connected = await ws_manager.start()

        if ws_connected:
            logger.info("WebSocket connected successfully")

            # Create and start WebSocket collectors (primary data source)
            orderbook_collector = OrderbookWebSocketCollector(db, ws_manager)
            trades_collector = TradesWebSocketCollector(db, ws_manager)
            candles_collector = CandleWebSocketCollector(db, ws_manager)
            all_mids_collector = AllMidsWebSocketCollector(db, ws_manager)

            await orderbook_collector.start()
            await trades_collector.start()
            await candles_collector.start()
            await all_mids_collector.start()

            logger.info("All WebSocket collectors started")
        else:
            logger.warning("WebSocket connection failed, using REST fallback")

    try:
        # Setup scheduler
        logger.info("Setting up scheduler...")
        scheduler = setup_scheduler()

        # Add jobs - pass ws_available to skip REST jobs when WS is active
        ws_available = ws_manager is not None and ws_manager.is_connected()
        add_jobs(scheduler, db, hl_client, cf_client, stats_client, ws_available=ws_available)

        # Run startup tasks
        logger.info("Running startup tasks...")
        ws_available = ws_manager is not None and ws_manager.is_connected()
        try:
            await run_startup_tasks(
                db, hl_client, cf_client, stats_client, ws_available=ws_available
            )
        except Exception as e:
            logger.error(f"Startup tasks failed: {e}")
            logger.warning("Continuing with scheduler...")

        # Initialize Persistent Trader WebSocket Manager AFTER startup tasks
        # (so traders are already in the database from leaderboard fetch)
        if settings.trader_ws_enabled:
            logger.info("Initializing Persistent Trader WebSocket Manager...")
            trader_ws_manager = PersistentTraderWebSocketManager(db)
            ws_started = await trader_ws_manager.start()

            if ws_started:
                logger.info(
                    f"Persistent Trader WebSocket Manager started (positions collection enabled)"
                )
            else:
                logger.warning("Failed to start Trader WebSocket Manager")

            # Initialize Persistent Trader Orders WebSocket Manager
            logger.info("Initializing Persistent Trader Orders WebSocket Manager...")
            trader_orders_ws_manager = PersistentTraderOrdersWSManager(db)
            orders_ws_started = await trader_orders_ws_manager.start()

            if orders_ws_started:
                logger.info(
                    "Persistent Trader Orders WebSocket Manager started "
                    f"(orders collection enabled)"
                )
            else:
                logger.warning("Failed to start Trader Orders WebSocket Manager")

        # Start scheduler
        logger.info("Starting scheduler...")
        scheduler.start()

        # Setup signal handlers
        shutdown_event = asyncio.Event()

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("System running. Press Ctrl+C to stop.")
        logger.info("-" * 60)

        # Wait for shutdown signal
        await shutdown_event.wait()

    finally:
        # Shutdown
        logger.info("Shutting down...")

        # Stop WebSocket collectors first
        if orderbook_collector:
            await orderbook_collector.stop()
        if trades_collector:
            await trades_collector.stop()
        if candles_collector:
            await candles_collector.stop()
        if all_mids_collector:
            await all_mids_collector.stop()
        if ws_manager:
            await ws_manager.stop()

        # Stop Trader WebSocket Managers
        if trader_ws_manager:
            await trader_ws_manager.stop()
        if trader_orders_ws_manager:
            await trader_orders_ws_manager.stop()

        # Shutdown scheduler
        if scheduler:
            scheduler.shutdown(wait=True)

        # Close API clients
        await hl_client.__aexit__(None, None, None)
        await cf_client.__aexit__(None, None, None)
        await stats_client.__aexit__(None, None, None)

        client.close()
        logger.info("Shutdown complete")


def run() -> None:
    """Run the application."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
