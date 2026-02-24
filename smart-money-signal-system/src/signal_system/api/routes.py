"""API Routes for signals and alerts."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from signal_system.api.dependencies import get_signal_processor, get_whale_detector, get_signal_store

router = APIRouter()


class SignalResponse(BaseModel):
    """Response model for trading signal."""

    symbol: str
    action: str
    confidence: float
    long_bias: float
    short_bias: float
    net_bias: float
    traders_long: int
    traders_short: int
    timestamp: str


class AlertResponse(BaseModel):
    """Response model for whale alert."""

    priority: str
    title: str
    description: str
    detected_at: str
    expires_at: str
    changes: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str


@router.get("/signals/latest", response_model=SignalResponse | None)
async def get_latest_signal() -> SignalResponse | None:
    """Get the latest trading signal.

    Returns:
        Latest signal or None if no signal generated yet
    """
    processor = get_signal_processor()
    signal = processor.get_latest_signal()

    if signal is None:
        return None

    return SignalResponse(**signal)


@router.get("/signals/history")
async def get_signal_history(limit: int = 100) -> list[dict[str, Any]]:
    """Get signal history.

    Args:
        limit: Maximum number of signals to return

    Returns:
        List of historical signals
    """
    store = get_signal_store()
    signals = store.get_signals(limit)

    return [
        {
            "symbol": s.symbol,
            "action": s.action,
            "confidence": s.confidence,
            "long_bias": s.long_bias,
            "short_bias": s.short_bias,
            "net_bias": s.net_bias,
            "traders_long": s.traders_long,
            "traders_short": s.traders_short,
            "timestamp": s.timestamp,
            "stored_at": s.stored_at,
        }
        for s in signals
    ]


@router.get("/signals/stats")
async def get_signal_stats() -> dict[str, Any]:
    """Get signal generation statistics.

    Returns:
        Signal processor statistics
    """
    processor = get_signal_processor()
    return processor.get_stats()


@router.get("/alerts/latest", response_model=AlertResponse | None)
async def get_latest_alert() -> AlertResponse | None:
    """Get the latest whale alert.

    Returns:
        Latest alert or None if no alerts
    """
    detector = get_whale_detector()
    alerts = detector.get_active_alerts()

    if not alerts:
        return None

    alert = alerts[-1]
    return AlertResponse(
        priority=alert.priority.value,
        title=alert.title,
        description=alert.description,
        detected_at=alert.detected_at,
        expires_at=alert.expires_at,
        changes=[
            {
                "address": c.address,
                "tier": c.tier,
                "coin": c.coin,
                "change_pct": c.change_pct,
                "account_value": c.account_value,
            }
            for c in alert.changes
        ],
    )


@router.get("/alerts/history")
async def get_alert_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get alert history.

    Args:
        limit: Maximum number of alerts to return

    Returns:
        List of historical alerts
    """
    detector = get_whale_detector()
    alerts = detector.get_recent_alerts(limit)

    return [
        {
            "priority": a.priority.value,
            "title": a.title,
            "description": a.description,
            "detected_at": a.detected_at,
            "expires_at": a.expires_at,
            "changes_count": len(a.changes),
        }
        for a in alerts
    ]


@router.get("/alerts/active")
async def get_active_alerts() -> list[dict[str, Any]]:
    """Get all active (non-expired) alerts.

    Returns:
        List of active alerts
    """
    detector = get_whale_detector()
    alerts = detector.get_active_alerts()

    return [
        {
            "priority": a.priority.value,
            "title": a.title,
            "description": a.description,
            "detected_at": a.detected_at,
            "expires_at": a.expires_at,
            "signal_impact": a.signal_impact,
            "changes": [
                {
                    "address": c.address,
                    "tier": c.tier,
                    "coin": c.coin,
                    "previous_szi": c.previous_szi,
                    "current_szi": c.current_szi,
                    "change_pct": c.change_pct,
                }
                for c in a.changes
            ],
        }
        for a in alerts
    ]


@router.get("/whales/stats")
async def get_whale_stats() -> dict[str, Any]:
    """Get whale detection statistics.

    Returns:
        Whale detector statistics
    """
    detector = get_whale_detector()
    return detector.get_stats()


@router.get("/signals/store/stats")
async def get_signal_store_stats() -> dict[str, Any]:
    """Get signal store statistics.

    Returns:
        Signal store statistics
    """
    store = get_signal_store()
    return {
        "signals": store.get_signal_stats(),
        "alerts": store.get_alert_stats(),
    }
