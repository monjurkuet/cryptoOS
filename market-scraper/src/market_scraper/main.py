"""Market scraper entry point — runs position monitor + API server."""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI

from market_scraper.api import router as api_router
from market_scraper.config import get_settings
from market_scraper.db import close_mongo, connect_mongo
from market_scraper.services.monitor import PositionMonitor

# Module-level app for uvicorn string import (e.g. "market_scraper.main:app")
app: FastAPI  # type: ignore[no-redef]

_log_configured = False


def _configure_logging() -> None:
    global _log_configured
    if _log_configured:
        return
    settings = get_settings()
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
    _log_configured = True


def _make_lifespan(monitor_task: asyncio.Task | None):
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await close_mongo()
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    return lifespan


def _create_app(monitor_task: asyncio.Task | None = None) -> FastAPI:
    _configure_logging()
    application = FastAPI(
        title="cryptoOS market-scraper",
        version="0.1.0",
        lifespan=_make_lifespan(monitor_task),
    )
    application.include_router(api_router)

    @application.get("/")
    async def root() -> dict[str, str]:
        return {"service": "market-scraper", "version": "0.1.0"}
    return application


def main() -> int:
    """Entry point: starts monitor + API server."""
    global app

    async def _run() -> int:
        _configure_logging()
        settings = get_settings()
        await connect_mongo(settings.mongo_url, settings.mongo_db)

        monitor = PositionMonitor()
        task = asyncio.create_task(monitor.run_forever())

        app = _create_app(monitor_task=task)

        config = uvicorn.Config(
            app,
            host=settings.api_host,
            port=settings.api_port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()
        return 0

    return asyncio.run(_run())


def build_app() -> FastAPI:
    """Build FastAPI app (for testing)."""
    _configure_logging()
    return _create_app(monitor_task=None)


if __name__ == "__main__":
    sys.exit(main())
