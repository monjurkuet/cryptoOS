# src/market_scraper/api/__init__.py

from typing import TYPE_CHECKING, Any

__all__ = ["app", "create_app"]

if TYPE_CHECKING:
    from fastapi import FastAPI

    app: "FastAPI"

    def create_app() -> "FastAPI": ...


def __getattr__(name: str) -> Any:
    """Lazily expose the FastAPI application objects."""
    if name in {"app", "create_app"}:
        from market_scraper.api.main import app, create_app

        exports = {"app": app, "create_app": create_app}
        return exports[name]

    raise AttributeError(f"module 'market_scraper.api' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Include lazily exported names in interactive discovery."""
    return sorted(__all__)
