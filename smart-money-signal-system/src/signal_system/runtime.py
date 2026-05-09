"""Shared runtime assembly for API and standalone execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pymongo import MongoClient
import structlog

from signal_system.config import SignalSystemSettings, get_settings
from signal_system.dashboard.store import DecisionTraceStore, ParamEventStore
from signal_system.event_subscriber import EventSubscriber
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.outcome_tracker import SignalOutcomeTracker
from signal_system.rl.parameter_server import RLParameterServer
from signal_system.runtime_config import SignalRuntimeConfig, SignalRuntimeConfigStore
from signal_system.services.event_processor import EventProcessor
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.weighting_engine.config import (
    PerformanceWeightConfig,
    RecencyWeightConfig,
    SizeWeightConfig,
    WeightingConfig,
)
from signal_system.weighting_engine.engine import TraderWeightingEngine
from signal_system.whale_alerts.detector import WhaleAlertDetector

logger = structlog.get_logger(__name__)

_SIGNAL_SYSTEM_ROOT = Path(__file__).parents[2]
_DEFAULT_CHECKPOINT_DIR = _SIGNAL_SYSTEM_ROOT / "checkpoints"


@dataclass
class RuntimeComponents:
    """Shared runtime components for standalone and API modes."""

    settings: SignalSystemSettings
    runtime_config: SignalRuntimeConfig
    config_store: SignalRuntimeConfigStore
    mongo_client: MongoClient | None
    event_subscriber: EventSubscriber
    signal_processor: SignalGenerationProcessor
    signal_store: SignalStore
    weighting_engine: TraderWeightingEngine
    whale_detector: WhaleAlertDetector
    outcome_tracker: SignalOutcomeTracker
    outcome_store: OutcomeStore
    trace_store: DecisionTraceStore
    param_event_store: ParamEventStore
    rl_param_server: RLParameterServer
    event_processor: EventProcessor


def build_runtime(
    settings: SignalSystemSettings | None = None,
    mongo_client_factory: Callable[..., MongoClient] = MongoClient,
    event_subscriber_factory: Callable[[Any], EventSubscriber] = EventSubscriber,
) -> RuntimeComponents:
    """Build runtime components from env settings plus YAML config."""
    resolved_settings = settings or get_settings()
    config_store = SignalRuntimeConfigStore(path=Path(resolved_settings.signal_config_path))
    runtime_config = config_store.load()
    _apply_config_to_settings(resolved_settings, runtime_config)

    mongo_client = _create_mongo_client(resolved_settings, mongo_client_factory)
    parameter_ranges = _parameter_ranges(runtime_config)
    defaults = runtime_config.parameters.defaults
    processor_cfg = runtime_config.signal_processor
    weighting_engine = TraderWeightingEngine(config=_build_weighting_config(runtime_config))

    signal_processor = SignalGenerationProcessor(
        symbol=processor_cfg.symbol,
        trader_ttl_seconds=processor_cfg.trader_ttl_seconds,
        max_traders=processor_cfg.max_traders,
        bias_threshold=defaults.bias_threshold,
        conf_scale=defaults.conf_scale,
        min_confidence=defaults.min_confidence,
        emit_bias_delta=processor_cfg.emit_bias_delta,
        decision_trace_buffer_size=processor_cfg.decision_trace_buffer_size,
        parameter_ranges=parameter_ranges,
        weighting_engine=weighting_engine,
    )
    signal_store = SignalStore(
        mongo_client=mongo_client,
        database_name=resolved_settings.mongo.database,
        retention_days=runtime_config.dashboard_retention_days,
    )
    whale_alert_cfg = runtime_config.whale_alerts
    whale_detector = WhaleAlertDetector(
        alpha_whale_threshold=whale_alert_cfg.alpha_whale_threshold,
        whale_threshold=whale_alert_cfg.whale_threshold,
        aggregation_window_minutes=whale_alert_cfg.aggregation_window_minutes,
        position_history_ttl=whale_alert_cfg.position_history_ttl,
        max_alerts=whale_alert_cfg.max_alerts,
        max_recent_changes=whale_alert_cfg.max_recent_changes,
    )

    outcome_cfg = runtime_config.outcome_tracking
    outcome_tracker = SignalOutcomeTracker(
        evaluation_horizons=outcome_cfg.evaluation_horizons,
        max_pending=outcome_cfg.max_pending,
        max_outcomes=outcome_cfg.max_outcomes,
    )
    outcome_store = OutcomeStore(
        mongo_client=mongo_client,
        database_name=resolved_settings.mongo.database,
    )
    trace_store = DecisionTraceStore(
        mongo_client=mongo_client,
        database_name=resolved_settings.mongo.database,
        retention_days=runtime_config.dashboard_retention_days,
    )
    param_event_store = ParamEventStore(
        mongo_client=mongo_client,
        database_name=resolved_settings.mongo.database,
        retention_days=runtime_config.dashboard_retention_days,
    )
    rl_param_server = RLParameterServer(
        bias_threshold=defaults.bias_threshold,
        conf_scale=defaults.conf_scale,
        min_confidence=defaults.min_confidence,
        checkpoint_dir=_resolve_checkpoint_dir(runtime_config),
        param_ranges=parameter_ranges,
    )
    if resolved_settings.load_rl_checkpoint_on_startup:
        rl_param_server.load_from_checkpoint()
    rl_params = rl_param_server.get_params()
    signal_processor.set_rl_params(**rl_params)
    param_event_store.store_event(rl_params, source="startup")
    logger.info("rl_params_loaded", **rl_params)

    event_subscriber = event_subscriber_factory(resolved_settings.redis)
    event_processor = EventProcessor(
        signal_processor=signal_processor,
        whale_detector=whale_detector,
        signal_store=signal_store,
        settings=resolved_settings,
        outcome_tracker=outcome_tracker,
        outcome_store=outcome_store,
        trace_store=trace_store,
    )

    return RuntimeComponents(
        settings=resolved_settings,
        runtime_config=runtime_config,
        config_store=config_store,
        mongo_client=mongo_client,
        event_subscriber=event_subscriber,
        signal_processor=signal_processor,
        signal_store=signal_store,
        weighting_engine=weighting_engine,
        whale_detector=whale_detector,
        outcome_tracker=outcome_tracker,
        outcome_store=outcome_store,
        trace_store=trace_store,
        param_event_store=param_event_store,
        rl_param_server=rl_param_server,
        event_processor=event_processor,
    )


def apply_runtime_config(
    components: RuntimeComponents,
    runtime_config: SignalRuntimeConfig,
    source: str,
) -> None:
    """Apply runtime config to a live runtime without process restart."""
    _apply_config_to_settings(components.settings, runtime_config)
    parameter_ranges = _parameter_ranges(runtime_config)
    defaults = runtime_config.parameters.defaults
    processor_cfg = runtime_config.signal_processor
    components.signal_processor.set_runtime_config(
        symbol=processor_cfg.symbol,
        trader_ttl_seconds=processor_cfg.trader_ttl_seconds,
        max_traders=processor_cfg.max_traders,
        emit_bias_delta=processor_cfg.emit_bias_delta,
        decision_trace_buffer_size=processor_cfg.decision_trace_buffer_size,
        parameter_ranges=parameter_ranges,
    )
    components.rl_param_server.set_param_ranges(parameter_ranges)
    components.rl_param_server.set_checkpoint_dir(_resolve_checkpoint_dir(runtime_config))
    components.rl_param_server.update_params(
        bias_threshold=defaults.bias_threshold,
        conf_scale=defaults.conf_scale,
        min_confidence=defaults.min_confidence,
    )
    current_params = components.rl_param_server.get_params()
    components.signal_processor.set_rl_params(**current_params)

    outcome_cfg = runtime_config.outcome_tracking
    components.outcome_tracker.set_runtime_config(
        evaluation_horizons=outcome_cfg.evaluation_horizons,
        max_pending=outcome_cfg.max_pending,
        max_outcomes=outcome_cfg.max_outcomes,
    )
    components.weighting_engine.set_config(_build_weighting_config(runtime_config))

    whale_cfg = runtime_config.whale_alerts
    components.whale_detector.set_runtime_config(
        alpha_whale_threshold=whale_cfg.alpha_whale_threshold,
        whale_threshold=whale_cfg.whale_threshold,
        aggregation_window_minutes=whale_cfg.aggregation_window_minutes,
        position_history_ttl=whale_cfg.position_history_ttl,
        max_alerts=whale_cfg.max_alerts,
        max_recent_changes=whale_cfg.max_recent_changes,
    )
    components.param_event_store.store_event(current_params, source=source)
    components.runtime_config = runtime_config


def _create_mongo_client(
    settings: SignalSystemSettings,
    mongo_client_factory: Callable[..., MongoClient],
) -> MongoClient | None:
    try:
        client = mongo_client_factory(settings.mongo.url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info("signal_system_mongo_connected")
        return client
    except Exception as error:
        logger.warning("signal_system_mongo_connection_failed", error=str(error))
        return None


def _build_weighting_config(runtime_config: SignalRuntimeConfig) -> WeightingConfig:
    cfg = runtime_config.weighting
    return WeightingConfig(
        performance=PerformanceWeightConfig(**cfg.performance.model_dump()),
        size=SizeWeightConfig(**cfg.size.model_dump()),
        recency=RecencyWeightConfig(**cfg.recency.model_dump()),
        performance_dimension_weight=cfg.performance_dimension_weight,
        size_dimension_weight=cfg.size_dimension_weight,
        recency_dimension_weight=cfg.recency_dimension_weight,
        regime_dimension_weight=cfg.regime_dimension_weight,
    )


def _parameter_ranges(runtime_config: SignalRuntimeConfig) -> dict[str, tuple[float, float]]:
    ranges = runtime_config.parameters.ranges
    return {
        "bias_threshold": (ranges.bias_threshold.min, ranges.bias_threshold.max),
        "conf_scale": (ranges.conf_scale.min, ranges.conf_scale.max),
        "min_confidence": (ranges.min_confidence.min, ranges.min_confidence.max),
    }


def _resolve_checkpoint_dir(runtime_config: SignalRuntimeConfig) -> Path:
    configured = runtime_config.improvement.checkpoint_dir.strip()
    if not configured:
        return _DEFAULT_CHECKPOINT_DIR
    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    return _SIGNAL_SYSTEM_ROOT / candidate


def _apply_config_to_settings(
    settings: SignalSystemSettings,
    runtime_config: SignalRuntimeConfig,
) -> None:
    settings.symbol = runtime_config.signal_processor.symbol
    settings.dashboard_retention_days = runtime_config.dashboard_retention_days
    settings.enable_rl_retrain_api = (
        settings.enable_rl_retrain_api or runtime_config.improvement.enable_retrain_api
    )
    settings.load_rl_checkpoint_on_startup = (
        settings.load_rl_checkpoint_on_startup
        or runtime_config.improvement.load_checkpoint_on_startup
    )
