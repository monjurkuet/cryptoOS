# src/market_scraper/connectors/coin_metrics/parsers.py

"""Response parsers for Coin Metrics data."""

from datetime import datetime
from typing import Any

from market_scraper.connectors.coin_metrics.config import CoinMetricsMetric
from market_scraper.core.events import StandardEvent


def parse_metrics_response(
    data: dict[str, Any],
    source: str = "coin_metrics",
) -> StandardEvent:
    """Parse Coin Metrics response into a StandardEvent.

    Args:
        data: Raw API response from Coin Metrics endpoint
        source: Source identifier for the event

    Returns:
        Standardized event containing metrics data

    Raises:
        ValueError: If required fields are missing or invalid
    """
    if "error" in data:
        raise ValueError(f"Coin Metrics API error: {data['error']}")

    data_points = data.get("data", [])
    if not data_points:
        raise ValueError("No data points in response")

    # Get latest data point
    latest = data_points[-1]
    timestamp = _parse_timestamp(latest.get("time", ""))
    asset = latest.get("asset", "btc")

    # Extract metrics
    metrics = {}
    for key, value in latest.items():
        if key not in ("asset", "time"):
            try:
                # Try to convert to float
                metrics[key] = float(value) if value else None
            except (ValueError, TypeError):
                metrics[key] = value

    return StandardEvent.create(
        event_type="coin_metrics",
        source=source,
        payload={
            "timestamp": timestamp.isoformat() if timestamp else None,
            "asset": asset,
            "metrics": metrics,
            "metrics_count": len(metrics),
        },
    )


def parse_metrics_historical(
    data: dict[str, Any],
    source: str = "coin_metrics",
) -> list[StandardEvent]:
    """Parse Coin Metrics historical data into a list of StandardEvents.

    Args:
        data: Raw API response from Coin Metrics endpoint
        source: Source identifier for the events

    Returns:
        List of standardized events, one per data point
    """
    if "error" in data:
        return []

    data_points = data.get("data", [])
    events = []

    for point in data_points:
        try:
            timestamp = _parse_timestamp(point.get("time", ""))
            asset = point.get("asset", "btc")

            metrics = {}
            for key, value in point.items():
                if key not in ("asset", "time"):
                    try:
                        metrics[key] = float(value) if value else None
                    except (ValueError, TypeError):
                        metrics[key] = value

            event = StandardEvent.create(
                event_type="coin_metrics_historical",
                source=source,
                payload={
                    "timestamp": timestamp.isoformat() if timestamp else None,
                    "asset": asset,
                    "metrics": metrics,
                },
            )
            events.append(event)
        except (KeyError, TypeError):
            continue

    return events


def parse_single_metric(
    data: dict[str, Any],
    metric: str,
    source: str = "coin_metrics",
) -> StandardEvent:
    """Parse a single metric from Coin Metrics response.

    Args:
        data: Raw API response from Coin Metrics endpoint
        metric: Metric name
        source: Source identifier for the event

    Returns:
        Standardized event containing single metric data
    """
    if "error" in data:
        raise ValueError(f"Coin Metrics API error: {data['error']}")

    data_points = data.get("data", [])
    if not data_points:
        raise ValueError(f"No data for metric: {metric}")

    # Build historical values
    historical = []
    for point in data_points:
        try:
            timestamp = _parse_timestamp(point.get("time", ""))
            value = point.get(metric)
            if value is not None:
                historical.append(
                    {
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "value": float(value),
                    }
                )
        except (KeyError, TypeError, ValueError):
            continue

    # Calculate statistics
    values = [h["value"] for h in historical if h.get("value") is not None]
    statistics = {
        "count": len(values),
        "average": sum(values) / len(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }

    return StandardEvent.create(
        event_type="coin_metrics_single",
        source=source,
        payload={
            "metric_name": metric,
            "description": _get_metric_description(metric),
            "current_value": historical[-1].get("value") if historical else None,
            "timestamp": historical[-1].get("timestamp") if historical else None,
            "statistics": statistics,
            "historical": historical,
        },
    )


def validate_metrics_data(data: dict[str, Any]) -> None:
    """Validate Coin Metrics data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Coin Metrics data must be a dictionary")

    if "error" in data:
        raise ValueError(f"API error: {data['error']}")

    data_points = data.get("data")
    if data_points is None:
        raise ValueError("Coin Metrics data missing 'data' field")

    if not isinstance(data_points, list):
        raise ValueError("'data' field must be a list")


def _parse_timestamp(time_str: str) -> datetime | None:
    """Parse Coin Metrics timestamp string.

    Args:
        time_str: ISO 8601 timestamp string

    Returns:
        Parsed datetime or None
    """
    if not time_str:
        return None

    try:
        # Handle ISO 8601 format with nanoseconds
        if "." in time_str:
            time_str = time_str.split(".")[0] + "Z"
        elif time_str.endswith("Z"):
            pass
        else:
            time_str = time_str + "Z"

        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _get_metric_description(metric: str) -> str:
    """Get human-readable description for a metric.

    Args:
        metric: Metric ID

    Returns:
        Description string
    """
    descriptions = {
        CoinMetricsMetric.PRICE_USD.value: "Bitcoin price in USD",
        CoinMetricsMetric.MARKET_CAP.value: "Market capitalization in USD",
        CoinMetricsMetric.ACTIVE_ADDRESSES.value: "Daily active addresses count",
        CoinMetricsMetric.TRANSACTION_COUNT.value: "Daily transaction count",
        CoinMetricsMetric.BLOCK_COUNT.value: "Daily block count",
        CoinMetricsMetric.SUPPLY_CURRENT.value: "Current circulating supply",
    }
    return descriptions.get(metric, f"Coin Metrics metric: {metric}")
