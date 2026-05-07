"""API Routes for signals and alerts."""

import asyncio
from datetime import UTC, datetime, timedelta
import secrets
from typing import Literal
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ValidationError
import structlog

from signal_system.api.dependencies import (
    get_mongo_client,
    get_outcome_store,
    get_param_event_store,
    get_rl_param_server,
    get_runtime_components,
    get_settings_ref,
    get_signal_processor,
    get_signal_config_store,
    get_signal_store,
    get_trace_store,
    get_whale_detector,
)
from signal_system.dashboard.store import normalize_market_scraper_signal
from signal_system.runtime import apply_runtime_config

router = APIRouter()
logger = structlog.get_logger(__name__)


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
    store = get_signal_store()
    signal = await asyncio.to_thread(store.get_latest_signal)

    if signal is None:
        return None

    return SignalResponse(
        symbol=signal.symbol,
        action=signal.action,
        confidence=signal.confidence,
        long_bias=signal.long_bias,
        short_bias=signal.short_bias,
        net_bias=signal.net_bias,
        traders_long=signal.traders_long,
        traders_short=signal.traders_short,
        timestamp=signal.timestamp,
    )


@router.get("/signal-system/signals/latest", response_model=SignalResponse | None)
async def get_latest_signal_namespaced() -> SignalResponse | None:
    """Compatibility-safe alias for latest signal endpoint."""
    return await get_latest_signal()


@router.get("/signals/history")
async def get_signal_history(limit: int = 100) -> list[dict[str, Any]]:
    """Get signal history.

    Args:
        limit: Maximum number of signals to return

    Returns:
        List of historical signals
    """
    store = get_signal_store()
    signals = await asyncio.to_thread(store.get_signals, limit)

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


@router.get("/signal-system/signals/history")
async def get_signal_history_namespaced(limit: int = 100) -> list[dict[str, Any]]:
    """Compatibility-safe alias for signal history endpoint."""
    return await get_signal_history(limit=limit)


@router.get("/signals/stats")
async def get_signal_stats() -> dict[str, Any]:
    """Get signal generation statistics.

    Returns:
        Signal processor statistics
    """
    processor = get_signal_processor()
    return processor.get_stats()


@router.get("/signal-system/signals/stats")
async def get_signal_stats_namespaced() -> dict[str, Any]:
    """Compatibility-safe alias for signal stats endpoint."""
    return await get_signal_stats()


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
    signal_stats = await asyncio.to_thread(store.get_signal_stats)
    alert_stats = await asyncio.to_thread(store.get_alert_stats)
    return {
        "signals": signal_stats,
        "alerts": alert_stats,
    }


@router.get("/signal-system/signals/store-stats")
async def get_signal_store_stats_namespaced() -> dict[str, Any]:
    """Compatibility-safe alias for signal store stats endpoint."""
    return await get_signal_store_stats()


def _assert_config_mutation_allowed(agent_token: str | None) -> None:
    settings = get_settings_ref()
    expected_token = settings.signal_admin_token.strip()
    if not expected_token:
        raise HTTPException(
            status_code=403,
            detail="Signal config mutations are disabled. Set SIGNAL_ADMIN_TOKEN to enable.",
        )
    if not agent_token or not secrets.compare_digest(agent_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Agent-Token")


def _extract_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept either raw config object or {config: {...}} envelope."""
    nested = payload.get("config")
    if isinstance(nested, dict):
        return nested
    return payload


@router.get("/config/signal")
async def get_signal_runtime_config() -> dict[str, Any]:
    """Return current live runtime config and config file path."""
    components = get_runtime_components()
    config_store = get_signal_config_store()
    settings = get_settings_ref()
    return {
        "config_path": str(config_store.path),
        "mutable": bool(settings.signal_admin_token.strip()),
        "config": components.runtime_config.model_dump(mode="json"),
    }


@router.post("/config/signal/validate")
async def validate_signal_runtime_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a candidate signal runtime config payload without applying it."""
    config_store = get_signal_config_store()
    raw_payload = _extract_config_payload(payload)
    try:
        validated = config_store.validate(raw_payload)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    return {
        "valid": True,
        "config": validated.model_dump(mode="json"),
    }


@router.put("/config/signal")
async def update_signal_runtime_config(
    payload: dict[str, Any],
    agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict[str, Any]:
    """Persist and apply runtime signal config from an agent-managed payload."""
    _assert_config_mutation_allowed(agent_token)
    config_store = get_signal_config_store()
    components = get_runtime_components()
    raw_payload = _extract_config_payload(payload)
    try:
        config = config_store.save_payload(raw_payload)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error

    apply_runtime_config(components=components, runtime_config=config, source="config_api")
    return {
        "status": "applied",
        "config_path": str(config_store.path),
        "config": config.model_dump(mode="json"),
    }


@router.post("/config/signal/reload")
async def reload_signal_runtime_config(
    agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> dict[str, Any]:
    """Reload runtime config from disk and apply it live."""
    _assert_config_mutation_allowed(agent_token)
    config_store = get_signal_config_store()
    components = get_runtime_components()
    config = config_store.load()
    apply_runtime_config(components=components, runtime_config=config, source="config_reload")
    return {
        "status": "reloaded",
        "config_path": str(config_store.path),
        "config": config.model_dump(mode="json"),
    }


# ── RL Endpoints ──────────────────────────────────────────────


class RLParamsUpdate(BaseModel):
    """Request body for updating RL params."""

    bias_threshold: float | None = None
    conf_scale: float | None = None
    min_confidence: float | None = None


class DashboardSignalPoint(BaseModel):
    source: Literal["signal_system", "market_scraper"]
    timestamp: str
    timestamp_ts: float
    action: str
    confidence: float
    long_bias: float
    short_bias: float
    net_bias: float
    traders_long: int
    traders_short: int


class DashboardOverviewResponse(BaseModel):
    window: str
    window_hours: int
    live: dict[str, Any]
    totals: dict[str, Any]
    outcomes_summary: dict[str, Any]


class DashboardTimelineResponse(BaseModel):
    source: Literal["all", "signal_system", "market_scraper"]
    count: int
    items: list[DashboardSignalPoint]


class DashboardParamsCurrentResponse(BaseModel):
    params: dict[str, float]
    last_updated: float
    checkpoint_path: str | None


class DashboardParamsHistoryEvent(BaseModel):
    source: str
    timestamp: str
    timestamp_ts: float
    params: dict[str, float]


class DashboardParamsHistoryResponse(BaseModel):
    count: int
    events: list[DashboardParamsHistoryEvent]


class DashboardDecisionTrace(BaseModel):
    timestamp: str = ""  # Derived from timestamp_ts if missing
    timestamp_ts: float
    symbol: str
    tracked_traders: int
    scored_traders: int
    weighted_long_score: float
    weighted_short_score: float
    total_weight: float
    bias_threshold: float = 0.2  # Default — not stored per-trace
    conf_scale: float = 1.0  # Default — not stored per-trace
    min_confidence: float = 0.3  # Default — not stored per-trace
    net_bias: float
    raw_confidence: float
    scaled_confidence: float
    action: str
    result: Literal["emitted", "suppressed"]
    reason_code: str

    def model_post_init(self, __context: Any) -> None:
        """Derive timestamp string from timestamp_ts if not provided."""
        if not self.timestamp and self.timestamp_ts:
            from datetime import UTC, datetime

            self.timestamp = datetime.fromtimestamp(self.timestamp_ts, tz=UTC).isoformat()


class DashboardDecisionResponse(BaseModel):
    count: int
    items: list[DashboardDecisionTrace]


def _parse_window_hours(window: str) -> int:
    normalized = (window or "24h").strip().lower()
    try:
        if normalized.endswith("h"):
            return max(1, int(normalized[:-1]))
        if normalized.endswith("d"):
            return max(1, int(normalized[:-1]) * 24)
    except ValueError:
        return 24
    return 24


def _to_ts(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


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
        server.update_params(**new_params)
    # Also push to signal processor
    processor = get_signal_processor()
    processor.set_rl_params(**server.get_params())
    param_store = get_param_event_store()
    await asyncio.to_thread(param_store.store_event, server.get_params(), "api_update")
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
    outcomes = await asyncio.to_thread(store.get_recent_outcomes, limit=limit)

    resolved = [o for o in outcomes if o.get("resolved_at") is not None]
    pnl_values = [o.get("pnl_pct", 0.0) for o in resolved if o.get("pnl_pct") is not None]

    return {
        "count": len(outcomes),
        "resolved_count": len(resolved),
        "outcomes": [
            {
                "signal_id": o.get("signal_id"),
                "action": o.get("action"),
                "confidence": o.get("confidence"),
                "pnl_pct": o.get("pnl_pct"),
                "timestamp": o.get("timestamp"),
                "resolved_at": o.get("resolved_at"),
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


@router.get(
    "/dashboard/signal-generator/overview",
    response_model=DashboardOverviewResponse,
)
async def get_dashboard_overview(window: str = "24h") -> DashboardOverviewResponse:
    """Get high-level dashboard data for signal generator internals."""
    window_hours = _parse_window_hours(window)
    cutoff_ts = (datetime.now(UTC) - timedelta(hours=window_hours)).timestamp()

    signal_store = get_signal_store()
    signal_rows = await asyncio.to_thread(signal_store.get_signals_in_window, from_ts=cutoff_ts, limit=5000)
    signal_actions: dict[str, int] = {}
    for row in signal_rows:
        signal_actions[row["action"]] = signal_actions.get(row["action"], 0) + 1

    market_rows: list[dict[str, Any]] = []
    mongo_client = get_mongo_client()
    settings = get_settings_ref()
    if mongo_client is not None:
        try:
            market_coll = mongo_client[settings.mongo.market_database]["signals"]

            def _query_market_signals() -> list[dict[str, Any]]:
                docs = list(
                    market_coll.find({"t": {"$gte": datetime.fromtimestamp(cutoff_ts, tz=UTC)}})
                    .sort("t", -1)
                    .limit(5000)
                )
                return [normalize_market_scraper_signal(doc) for doc in docs]

            market_rows = await asyncio.to_thread(_query_market_signals)
        except Exception as error:
            logger.warning("dashboard_market_query_failed", error=str(error))
            market_rows = []

    market_actions: dict[str, int] = {}
    for row in market_rows:
        market_actions[row["action"]] = market_actions.get(row["action"], 0) + 1

    outcome_store = get_outcome_store()
    outcomes = await asyncio.to_thread(outcome_store.get_recent_outcomes, limit=1000)
    pnl_values = [o.get("pnl_pct", 0.0) for o in outcomes if o.get("pnl_pct") is not None]
    win_rate = (
        len([value for value in pnl_values if value > 0]) / len(pnl_values)
        if pnl_values
        else 0.0
    )

    processor = get_signal_processor()
    rl_server = get_rl_param_server()
    trace_store = get_trace_store()
    trace_stats = await asyncio.to_thread(trace_store.get_stats)
    return DashboardOverviewResponse(
        window=window,
        window_hours=window_hours,
        live={
            "signal_processor": processor.get_stats(),
            "rl_status": rl_server.get_status(),
            "trace_store": trace_stats,
        },
        totals={
            "signal_system_count": len(signal_rows),
            "signal_system_actions": signal_actions,
            "market_scraper_count": len(market_rows),
            "market_scraper_actions": market_actions,
        },
        outcomes_summary={
            "count": len(outcomes),
            "avg_pnl": sum(pnl_values) / len(pnl_values) if pnl_values else 0.0,
            "win_rate": win_rate,
        },
    )


@router.get(
    "/dashboard/signal-generator/timeline",
    response_model=DashboardTimelineResponse,
)
async def get_dashboard_timeline(
    source: Literal["all", "signal_system", "market_scraper"] = "all",
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> DashboardTimelineResponse:
    """Get normalized timeline from signal-system and market-scraper sources."""
    from_ts = _to_ts(from_time)
    to_ts = _to_ts(to_time)

    items: list[dict[str, Any]] = []
    if source in ("all", "signal_system"):
        signal_store = get_signal_store()
        rows = await asyncio.to_thread(signal_store.get_signals_in_window, from_ts=from_ts, to_ts=to_ts, limit=limit)
        items.extend(rows)

    if source in ("all", "market_scraper"):
        mongo_client = get_mongo_client()
        settings = get_settings_ref()
        if mongo_client is not None:
            query: dict[str, Any] = {}
            if from_ts is not None or to_ts is not None:
                query["t"] = {}
            if from_ts is not None:
                query["t"]["$gte"] = datetime.fromtimestamp(from_ts, tz=UTC)
            if to_ts is not None:
                query["t"]["$lte"] = datetime.fromtimestamp(to_ts, tz=UTC)
            try:
                coll = mongo_client[settings.mongo.market_database]["signals"]

                def _query_market_timeline() -> list[dict[str, Any]]:
                    docs = list(coll.find(query).sort("t", -1).limit(limit))
                    return [normalize_market_scraper_signal(doc) for doc in docs]

                market_rows = await asyncio.to_thread(_query_market_timeline)
                items.extend(market_rows)
            except Exception as error:
                logger.warning("dashboard_market_query_failed", error=str(error))

    items.sort(key=lambda row: row.get("timestamp_ts", 0.0), reverse=True)
    items = items[:limit]
    points = [DashboardSignalPoint(**item) for item in items]
    return DashboardTimelineResponse(source=source, count=len(points), items=points)


@router.get(
    "/dashboard/signal-generator/params/current",
    response_model=DashboardParamsCurrentResponse,
)
async def get_dashboard_params_current() -> DashboardParamsCurrentResponse:
    """Get current RL runtime parameters and metadata."""
    status = get_rl_param_server().get_status()
    return DashboardParamsCurrentResponse(
        params=status.get("params", {}),
        last_updated=float(status.get("last_updated", 0.0)),
        checkpoint_path=status.get("checkpoint_path"),
    )


@router.get(
    "/dashboard/signal-generator/params/history",
    response_model=DashboardParamsHistoryResponse,
)
async def get_dashboard_params_history(
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> DashboardParamsHistoryResponse:
    """Get runtime parameter update history."""
    rows = await asyncio.to_thread(
        get_param_event_store().get_events,
        from_ts=_to_ts(from_time),
        to_ts=_to_ts(to_time),
        limit=limit,
    )
    events = [DashboardParamsHistoryEvent(**row) for row in rows]
    return DashboardParamsHistoryResponse(count=len(events), events=events)


@router.get(
    "/dashboard/signal-generator/decisions",
    response_model=DashboardDecisionResponse,
)
async def get_dashboard_decisions(
    result: Literal["emitted", "suppressed"] | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> DashboardDecisionResponse:
    """Get persisted signal decision traces for explainability panels."""
    rows = await asyncio.to_thread(
        get_trace_store().get_traces,
        from_ts=_to_ts(from_time),
        to_ts=_to_ts(to_time),
        limit=limit,
        result=result,
    )
    items = [DashboardDecisionTrace(**row) for row in rows]
    return DashboardDecisionResponse(count=len(items), items=items)


@router.post("/rl/retrain")
async def trigger_retrain(episodes: int | None = None) -> dict[str, Any]:
    """Trigger an RL retraining run (background).

    Args:
        episodes: Number of training episodes

    Returns:
        Status indicating retraining was initiated
    """
    settings = get_settings_ref()
    if not settings.enable_rl_retrain_api:
        return {
            "status": "disabled",
            "message": "RL retraining API is disabled in this runtime profile",
        }

    runtime_components = get_runtime_components()
    default_episodes = runtime_components.runtime_config.improvement.default_retrain_episodes
    selected_episodes = episodes if episodes is not None and episodes > 0 else default_episodes

    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent.parent.parent.parent
    cmd = [
        sys.executable, "-m", "signal_system.rl.retrain",
        "--episodes", str(selected_episodes),
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
        "episodes": selected_episodes,
        "message": "Training started in background. Check /rl/status for updates.",
    }
