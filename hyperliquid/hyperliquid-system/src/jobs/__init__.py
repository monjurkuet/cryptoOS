"""
Jobs Package.

This module provides scheduled job modules for data collection.
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
from src.jobs.scheduler import add_jobs, run_startup_tasks, setup_scheduler
from src.jobs.trader_orders import collect_trader_orders
from src.jobs.trader_positions import collect_all_positions

__all__ = [
    # Scheduler
    "setup_scheduler",
    "add_jobs",
    "run_startup_tasks",
    # BTC Market Data
    "collect_candles",
    "collect_orderbook",
    "collect_trades",
    "update_ticker",
    "collect_funding",
    "collect_daily_stats",
    # Trader Tracking
    "fetch_leaderboard",
    "update_tracked_traders",
    "collect_all_positions",
    "collect_trader_orders",
    # Signals
    "generate_signals",
    # Archive
    "archive_all_collections",
]
