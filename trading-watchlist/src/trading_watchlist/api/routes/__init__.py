"""API routers."""

from fastapi import APIRouter

from trading_watchlist.api.routes import health, rules

router = APIRouter()
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(rules.router, prefix="/api/v1", tags=["watchlist"])
