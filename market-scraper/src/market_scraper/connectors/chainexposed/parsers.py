# src/market_scraper/connectors/chainexposed/parsers.py

"""Parsers for ChainExposed data."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import StandardEvent


def parse_chainexposed_metric(data: dict[str, Any], source: str = "chainexposed") -> StandardEvent:
    """Parse ChainExposed metric data into StandardEvent.

    Args:
        data: Raw metric data from client
        source: Source identifier

    Returns:
        StandardEvent with metric data
    """
    metric_name = data.get("metric_name", "unknown")
    dates = data.get("dates", [])
    values = data.get("values", [])
    all_traces = data.get("all_traces", {})

    # Find latest non-null value
    latest_value = None
    latest_date = None
    for i in range(len(values) - 1, -1, -1):
        if values[i] is not None:
            latest_value = values[i]
            latest_date = dates[i]
            break

    # Build historical data (last 365 days)
    historical = []
    for i, (date, value) in enumerate(zip(dates, values)):
        if value is not None:
            historical.append({
                "date": date,
                "value": value,
            })

    # Keep only last 365 days
    historical = historical[-365:]

    # Calculate statistics
    valid_values = [v for v in values if v is not None]
    stats = {}
    if valid_values:
        stats = {
            "count": len(valid_values),
            "min": min(valid_values),
            "max": max(valid_values),
            "mean": sum(valid_values) / len(valid_values),
        }

    return StandardEvent.create(
        source=source,
        event_type="onchain_metric",
        payload={
            "metric_name": metric_name,
            "value": latest_value,
            "date": latest_date,
            "statistics": stats,
            "historical": historical,
            "traces": list(all_traces.keys()) if all_traces else [],
        },
    )


def parse_chainexposed_sopr(data: dict[str, Any]) -> StandardEvent:
    """Parse SOPR data with all variants.

    Args:
        data: Raw SOPR data from client

    Returns:
        StandardEvent with SOPR data including LTH/STH variants
    """
    event = parse_chainexposed_metric(data)

    # Add SOPR-specific interpretation
    value = event.payload.get("value")
    if value is not None:
        if value > 1.0:
            event.payload["interpretation"] = "profit_taking"  # Coins being sold at profit
        elif value < 1.0:
            event.payload["interpretation"] = "loss-realization"  # Coins being sold at loss
        else:
            event.payload["interpretation"] = "neutral"

    return event


def parse_chainexposed_nupl(data: dict[str, Any]) -> StandardEvent:
    """Parse NUPL data with interpretation.

    Args:
        data: Raw NUPL data from client

    Returns:
        StandardEvent with NUPL data and zone classification
    """
    event = parse_chainexposed_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # NUPL zones
        if value < 0:
            event.payload["zone"] = "capitulation"
        elif value < 0.25:
            event.payload["zone"] = "hope-fear"
        elif value < 0.5:
            event.payload["zone"] = "optimism"
        elif value < 0.75:
            event.payload["zone"] = "belief"
        else:
            event.payload["zone"] = "euphoria"

    return event


def parse_chainexposed_mvrv(data: dict[str, Any]) -> StandardEvent:
    """Parse MVRV data.

    Args:
        data: Raw MVRV data from client

    Returns:
        StandardEvent with MVRV data
    """
    event = parse_chainexposed_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # MVRV interpretation (rough guidelines)
        if value < 1.0:
            event.payload["signal"] = "undervalued"
        elif value > 3.5:
            event.payload["signal"] = "overvalued"
        else:
            event.payload["signal"] = "neutral"

    return event


def parse_chainexposed_hodl_waves(data: dict[str, Any]) -> StandardEvent:
    """Parse HODL Waves data (multi-trace metric).

    HODL Waves shows the distribution of Bitcoin by age bands.

    Args:
        data: Raw HODL Waves data from client

    Returns:
        StandardEvent with HODL Waves data
    """
    all_traces = data.get("all_traces", {})

    # Build band distribution
    bands = {}
    for trace_name, trace_data in all_traces.items():
        dates = trace_data.get("dates", [])
        values = trace_data.get("values", [])

        if dates and values:
            # Get latest non-null value
            latest_value = None
            for i in range(len(values) - 1, -1, -1):
                if values[i] is not None:
                    latest_value = values[i]
                    break

            bands[trace_name] = {
                "value": latest_value,
                "historical": [
                    {"date": d, "value": v}
                    for d, v in zip(dates[-365:], values[-365:])
                    if v is not None
                ],
            }

    return StandardEvent.create(
        source="chainexposed",
        event_type="onchain_metric",
        payload={
            "metric_name": "HODL_WAVES",
            "bands": bands,
            "band_count": len(bands),
        },
    )


def parse_chainexposed_dormancy(data: dict[str, Any]) -> StandardEvent:
    """Parse Dormancy data.

    Dormancy measures the average number of days destroyed per coin transacted.

    Args:
        data: Raw Dormancy data from client

    Returns:
        StandardEvent with Dormancy data
    """
    event = parse_chainexposed_metric(data)

    # Higher dormancy = older coins moving
    value = event.payload.get("value")
    stats = event.payload.get("statistics", {})

    if value is not None and stats.get("mean"):
        mean = stats["mean"]
        if value > mean * 1.5:
            event.payload["signal"] = "old_coins_moving"  # Potential distribution
        elif value < mean * 0.5:
            event.payload["signal"] = "young_coins_dominant"  # HODLing
        else:
            event.payload["signal"] = "normal"

    return event


def validate_chainexposed_data(data: dict[str, Any]) -> None:
    """Validate ChainExposed data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    if "metric_name" not in data:
        raise ValueError("Data must contain 'metric_name'")

    dates = data.get("dates", [])
    values = data.get("values", [])

    if not dates or not values:
        # Allow empty data but log warning
        return

    if len(dates) != len(values):
        raise ValueError(
            f"Dates and values length mismatch: {len(dates)} vs {len(values)}"
        )
