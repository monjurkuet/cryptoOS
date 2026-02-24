"""Dependency injection for API routes."""

from signal_system.event_subscriber import EventSubscriber
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector

# Global component references (set by main.py during startup)
_signal_processor: SignalGenerationProcessor | None = None
_whale_detector: WhaleAlertDetector | None = None
_event_subscriber: EventSubscriber | None = None
_signal_store: SignalStore | None = None


def set_components(
    signal_processor: SignalGenerationProcessor,
    whale_detector: WhaleAlertDetector,
    event_subscriber: EventSubscriber | None = None,
    signal_store: SignalStore | None = None,
) -> None:
    """Set global component references."""
    global _signal_processor, _whale_detector, _event_subscriber, _signal_store
    _signal_processor = signal_processor
    _whale_detector = whale_detector
    _event_subscriber = event_subscriber
    _signal_store = signal_store


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
