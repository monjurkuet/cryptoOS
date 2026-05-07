"""Dependency injection for API routes."""

from signal_system.event_subscriber import EventSubscriber
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.parameter_server import RLParameterServer
from signal_system.dashboard.store import DecisionTraceStore, ParamEventStore
from signal_system.config import SignalSystemSettings
from signal_system.runtime import RuntimeComponents
from signal_system.runtime_config import SignalRuntimeConfigStore

# Global component references (set by main.py during startup)
_signal_processor: SignalGenerationProcessor | None = None
_whale_detector: WhaleAlertDetector | None = None
_event_subscriber: EventSubscriber | None = None
_signal_store: SignalStore | None = None
_outcome_store: OutcomeStore | None = None
_rl_param_server: RLParameterServer | None = None
_trace_store: DecisionTraceStore | None = None
_param_event_store: ParamEventStore | None = None
_mongo_client = None
_settings: SignalSystemSettings | None = None
_runtime_components: RuntimeComponents | None = None
_signal_config_store: SignalRuntimeConfigStore | None = None


def set_components(
    signal_processor: SignalGenerationProcessor,
    whale_detector: WhaleAlertDetector,
    event_subscriber: EventSubscriber | None = None,
    signal_store: SignalStore | None = None,
    outcome_store: OutcomeStore | None = None,
    rl_param_server: RLParameterServer | None = None,
    trace_store: DecisionTraceStore | None = None,
    param_event_store: ParamEventStore | None = None,
    mongo_client=None,
    settings: SignalSystemSettings | None = None,
    runtime_components: RuntimeComponents | None = None,
    signal_config_store: SignalRuntimeConfigStore | None = None,
) -> None:
    """Set global component references."""
    global _signal_processor, _whale_detector, _event_subscriber, _signal_store, _outcome_store, _rl_param_server, _trace_store, _param_event_store, _mongo_client, _settings, _runtime_components, _signal_config_store
    _signal_processor = signal_processor
    _whale_detector = whale_detector
    _event_subscriber = event_subscriber
    _signal_store = signal_store
    _outcome_store = outcome_store
    _rl_param_server = rl_param_server
    _trace_store = trace_store
    _param_event_store = param_event_store
    _mongo_client = mongo_client
    _settings = settings
    _runtime_components = runtime_components
    _signal_config_store = signal_config_store


def get_signal_processor() -> SignalGenerationProcessor:
    """Get signal processor instance."""
    if _signal_processor is None:
        raise RuntimeError("Signal processor not initialized")
    return _signal_processor


def get_whale_detector() -> WhaleAlertDetector:
    """Get whale detector instance."""
    if _whale_detector is None:
        raise RuntimeError("Whale detector not initialized")
    return _whale_detector


def get_event_subscriber() -> EventSubscriber | None:
    """Get event subscriber instance."""
    return _event_subscriber


def get_signal_store() -> SignalStore:
    """Get signal store instance."""
    if _signal_store is None:
        raise RuntimeError("Signal store not initialized")
    return _signal_store


def get_outcome_store() -> OutcomeStore:
    """Get outcome store instance."""
    if _outcome_store is None:
        raise RuntimeError("Outcome store not initialized")
    return _outcome_store


def get_rl_param_server() -> RLParameterServer:
    """Get RL parameter server instance."""
    if _rl_param_server is None:
        raise RuntimeError("RL parameter server not initialized")
    return _rl_param_server


def get_trace_store() -> DecisionTraceStore:
    """Get decision trace store."""
    if _trace_store is None:
        raise RuntimeError("Decision trace store not initialized")
    return _trace_store


def get_param_event_store() -> ParamEventStore:
    """Get parameter event store."""
    if _param_event_store is None:
        raise RuntimeError("Param event store not initialized")
    return _param_event_store


def get_mongo_client():
    """Get shared Mongo client if configured."""
    return _mongo_client


def get_settings_ref() -> SignalSystemSettings:
    """Get settings snapshot used at startup."""
    if _settings is None:
        raise RuntimeError("Settings not initialized")
    return _settings


def get_runtime_components() -> RuntimeComponents:
    """Get assembled runtime components for config reload operations."""
    if _runtime_components is None:
        raise RuntimeError("Runtime components not initialized")
    return _runtime_components


def get_signal_config_store() -> SignalRuntimeConfigStore:
    """Get YAML config store used by runtime endpoints."""
    if _signal_config_store is None:
        raise RuntimeError("Signal config store not initialized")
    return _signal_config_store
