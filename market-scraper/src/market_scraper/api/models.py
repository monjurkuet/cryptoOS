# src/market_scraper/api/models.py

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus
    version: str
    components: dict[str, Any] = Field(default_factory=dict)


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    ready: bool
    checks: dict[str, bool] = Field(default_factory=dict)


class MarketDataResponse(BaseModel):
    """Market data response."""

    symbol: str
    price: float | None = None
    volume: float | None = None
    timestamp: datetime
    bid: float | None = None
    ask: float | None = None
    source: str


class OHLCVResponse(BaseModel):
    """OHLCV candle data response."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    count: int = 0


class MarketHistoryParams(BaseModel):
    """Query parameters for market history."""

    timeframe: str = Field(default="1m", description="Timeframe (1m, 5m, 15m, 1h, 1d)")
    start_time: datetime | None = Field(None, description="Start time (inclusive)")
    end_time: datetime | None = Field(None, description="End time (inclusive)")
    limit: int = Field(default=100, ge=1, le=10000, description="Max results")


class ConnectorStatusResponse(BaseModel):
    """Connector status response."""

    name: str
    status: str
    connected: bool
    last_heartbeat: datetime | None = None


class ConnectorHealthResponse(BaseModel):
    """Connector health response."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str = ""


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None
    code: int = 500
