"""Trading watchlist API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trading_watchlist.api.routes import router
from trading_watchlist.config import get_settings


def create_app() -> FastAPI:
    """Application factory."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="Trading watchlist API backed by structured JSON with markdown fallback",
        version=settings.app_version,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
