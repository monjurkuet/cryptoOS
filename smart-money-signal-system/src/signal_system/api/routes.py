"""API Routes for signals and alerts."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from signal_system.api.dependencies import (
    get_signal_processor,
    get_whale_detector,
    get_signal_store,
    get_outcome_store,
    get_rl_param_server,
)

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


# ── RL Endpoints ──────────────────────────────────────────────


class RLParamsUpdate(BaseModel):
    """Request body for updating RL params."""

    bias_threshold: float | None = None
    conf_scale: float | None = None
    min_confidence: float | None = None
    trend_weight: float | None = None
    volume_weight: float | None = None
    momentum_weight: float | None = None
    volatility_weight: float | None = None


@router.get("/rl/status")
async def get_rl_status() -> dict[str, Any]:
    """Get RL agent status including current params and metadata.

    Returns:
        RL parameter server status
    """
    server = get_rl_param_server()
    return server.get_status()


@router.get("/rl/params")
async def get_rl_params() -> dict[str, Any]:
    """Get current RL-adjusted signal parameters.

    Returns:
        Current signal parameters from the RL agent
    """
    server = get_rl_param_server()
    return {"params": server.get_params()}


@router.put("/rl/params")
async def update_rl_params(update: RLParamsUpdate) -> dict[str, Any]:
    """Update RL signal parameters (e.g. after retraining).

    Args:
        update: Parameters to update (only non-None fields are applied)

    Returns:
        Updated parameter values
    """
    server = get_rl_param_server()
    # Build dict of only provided fields
    new_params = {k: v for k, v in update.model_dump().items() if v is not None}
    if new_params:
        server.update_params(new_params)
        # Also push to signal processor
        processor = get_signal_processor()
        processor.set_rl_params(server.get_params())
    return {"params": server.get_params()}


@router.get("/rl/outcomes")
async def get_rl_outcomes(limit: int = 100) -> dict[str, Any]:
    """Get recent signal outcomes for RL training.

    Args:
        limit: Maximum outcomes to return

    Returns:
        Recent outcomes with summary stats
    """
    store = get_outcome_store()
    outcomes = store.get_recent_outcomes(limit=limit)

    resolved = [o for o in outcomes if o.resolved_at is not None]
    pnl_values = [o.pnl_pct for o in resolved if o.pnl_pct is not None]

    return {
        "count": len(outcomes),
        "resolved_count": len(resolved),
        "outcomes": [
            {
                "signal_id": o.signal_id,
                "action": o.action,
                "confidence": o.confidence,
                "pnl_pct": o.pnl_pct,
                "timestamp": o.timestamp,
                "resolved_at": o.resolved_at,
            }
            for o in outcomes
        ],
        "summary": {
            "total_signals": len(outcomes),
            "resolved_signals": len(resolved),
            "avg_pnl": sum(pnl_values) / len(pnl_values) if pnl_values else 0.0,
            "win_rate": (
                len([p for p in pnl_values if p > 0]) / len(pnl_values)
                if pnl_values
                else 0.0
            ),
        },
    }


@router.post("/rl/retrain")
async def trigger_retrain(episodes: int = 100) -> dict[str, Any]:
    """Trigger an RL retraining run (background).

    Args:
        episodes: Number of training episodes

    Returns:
        Status indicating retraining was initiated
    """
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    cmd = [
        sys.executable, "-m", "signal_system.rl.retrain",
        "--episodes", str(episodes),
        "--push",
    ]
    subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {
        "status": "retraining_initiated",
        "episodes": episodes,
        "message": "Training started in background. Check /rl/status for updates.",
    }

