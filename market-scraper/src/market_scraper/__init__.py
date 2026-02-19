# src/market_scraper/__init__.py

"""Market Scraper Framework.

A real-time market data aggregation and distribution system.
"""

__version__ = "0.1.0"

from market_scraper.api import app, create_app
from market_scraper.orchestration import HealthMonitor, LifecycleManager, Scheduler

__all__ = [
    "__version__",
    "app",
    "create_app",
    "LifecycleManager",
    "Scheduler",
    "HealthMonitor",
]
