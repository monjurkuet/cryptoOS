# src/market_scraper/api/main.py

import asyncio
from contextlib import asynccontextmanager, suppress

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from market_scraper.api.routes import (
    cbbi,
    connectors,
    health,
    markets,
    onchain,
    signals,
    traders,
    websocket,
)
from market_scraper.api.dependencies import get_connector_factory
from market_scraper.core.config import get_settings
from market_scraper.orchestration.lifecycle import LifecycleManager

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with non-blocking startup.

    The HTTP server starts immediately, allowing access to API docs
    and health endpoints while MongoDB connects in the background.
    """
    lifecycle = LifecycleManager()
    app.state.lifecycle = lifecycle
    settings = get_settings()

    logger.info(
        "api_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        symbol=settings.hyperliquid.symbol,
    )

    # Start lifecycle in background - don't block HTTP server startup
    startup_task = asyncio.create_task(lifecycle.startup_background())

    yield

    logger.info("api_shutting_down")

    # Close all connectors
    try:
        connector_factory = get_connector_factory()
        await connector_factory.close_all()
    except Exception as e:
        logger.warning("connector_close_error", error=str(e))

    # Cancel background startup if still running
    if not startup_task.done():
        startup_task.cancel()
        with suppress(asyncio.CancelledError):
            await startup_task

    await lifecycle.shutdown()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Market Scraper API",
        description="Real-time market data aggregation and distribution",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(markets.router, prefix="/api/v1/markets", tags=["markets"])
    app.include_router(connectors.router, prefix="/api/v1/connectors", tags=["connectors"])
    app.include_router(traders.router, prefix="/api/v1/traders", tags=["traders"])
    app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
    app.include_router(cbbi.router, prefix="/api/v1/cbbi", tags=["cbbi"])
    app.include_router(onchain.router, prefix="/api/v1/onchain", tags=["onchain"])
    app.include_router(websocket.router, tags=["websocket"])

    return app


app = create_app()
