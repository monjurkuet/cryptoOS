# src/market_scraper/utils/metrics.py

"""Prometheus metrics for the Market Scraper Framework."""


from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Event metrics
EVENTS_PUBLISHED = Counter(
    "market_scraper_events_published_total",
    "Total number of events published",
    ["event_type", "source"],
)

EVENTS_DELIVERED = Counter(
    "market_scraper_events_delivered_total",
    "Total number of events delivered to handlers",
    ["event_type"],
)

EVENTS_DROPPED = Counter(
    "market_scraper_events_dropped_total",
    "Total number of events dropped",
    ["event_type", "reason"],
)

EVENT_PROCESSING_TIME = Histogram(
    "market_scraper_event_processing_seconds",
    "Time spent processing events",
    ["event_type"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Connector metrics
CONNECTOR_HEALTH = Gauge(
    "market_scraper_connector_health",
    "Health status of connectors (1=healthy, 0=unhealthy)",
    ["connector_name"],
)

CONNECTOR_CONNECTIONS = Gauge(
    "market_scraper_connector_connections",
    "Number of active connections per connector",
    ["connector_name"],
)

# Storage metrics
STORAGE_OPERATIONS = Counter(
    "market_scraper_storage_operations_total",
    "Total storage operations",
    ["operation", "status"],
)

STORAGE_LATENCY = Histogram(
    "market_scraper_storage_latency_seconds",
    "Storage operation latency",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)


def start_metrics_server(port: int = 8000) -> None:
    """Start the Prometheus metrics HTTP server.

    Args:
        port: Port to listen on
    """
    start_http_server(port)


def record_event_published(event_type: str, source: str) -> None:
    """Record an event publication.

    Args:
        event_type: Type of event
        source: Event source
    """
    EVENTS_PUBLISHED.labels(event_type=event_type, source=source).inc()


def record_event_delivered(event_type: str) -> None:
    """Record an event delivery.

    Args:
        event_type: Type of event
    """
    EVENTS_DELIVERED.labels(event_type=event_type).inc()


def record_event_dropped(event_type: str, reason: str) -> None:
    """Record an event drop.

    Args:
        event_type: Type of event
        reason: Reason for dropping
    """
    EVENTS_DROPPED.labels(event_type=event_type, reason=reason).inc()


def set_connector_health(connector_name: str, healthy: bool) -> None:
    """Set connector health status.

    Args:
        connector_name: Name of the connector
        healthy: Whether the connector is healthy
    """
    CONNECTOR_HEALTH.labels(connector_name=connector_name).set(1 if healthy else 0)


def set_connector_connections(connector_name: str, count: int) -> None:
    """Set number of active connections.

    Args:
        connector_name: Name of the connector
        count: Number of connections
    """
    CONNECTOR_CONNECTIONS.labels(connector_name=connector_name).set(count)
