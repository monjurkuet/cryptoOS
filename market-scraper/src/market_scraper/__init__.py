# src/market_scraper/__init__.py

"""Market Scraper Framework.

A real-time market data aggregation and distribution system.
"""

from typing import TYPE_CHECKING, Any

__version__ = "0.1.0"

if TYPE_CHECKING:
    from fastapi import FastAPI

    from market_scraper.orchestration import HealthMonitor, LifecycleManager, Scheduler

    app: "FastAPI"

    def create_app() -> "FastAPI": ...


__all__ = [
    "__version__",
    "app",
    "create_app",
    "LifecycleManager",
    "Scheduler",
    "HealthMonitor",
]


def __getattr__(name: str) -> Any:
    """Lazily expose package-level application and orchestration symbols."""
    if name in {"app", "create_app"}:
        from market_scraper.api import app, create_app

        exports = {"app": app, "create_app": create_app}
        return exports[name]

    if name in {"LifecycleManager", "Scheduler", "HealthMonitor"}:
        from market_scraper.orchestration import HealthMonitor, LifecycleManager, Scheduler

        exports = {
            "LifecycleManager": LifecycleManager,
            "Scheduler": Scheduler,
            "HealthMonitor": HealthMonitor,
        }
        return exports[name]

    raise AttributeError(f"module 'market_scraper' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Include lazily exported names in interactive discovery."""
    return sorted(__all__)
