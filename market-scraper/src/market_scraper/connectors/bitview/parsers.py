# src/market_scraper/connectors/bitview/parsers.py

"""Parsers for Bitview data."""

from typing import Any

from market_scraper.core.events import StandardEvent


def parse_bitview_metric(data: dict[str, Any], source: str = "bitview") -> StandardEvent:
    """Parse Bitview metric data into StandardEvent.

    Args:
        data: Raw metric data from client
        source: Source identifier

    Returns:
        StandardEvent with metric data
    """
    metric_name = data.get("metric_name", "unknown")
    latest_value = data.get("latest_value")
    latest_date = data.get("latest_date")
    historical = data.get("historical", [])
    statistics = data.get("statistics", {})

    return StandardEvent.create(
        source=source,
        event_type="onchain_metric",
        payload={
            "metric_name": metric_name,
            "value": latest_value,
            "date": latest_date,
            "statistics": statistics,
            "historical": historical,
        },
    )


def parse_bitview_sopr(data: dict[str, Any]) -> StandardEvent:
    """Parse SOPR data with interpretation.

    Args:
        data: Raw SOPR data from client

    Returns:
        StandardEvent with SOPR data including interpretation
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        if value > 1.0:
            event.payload["interpretation"] = "profit_taking"
        elif value < 1.0:
            event.payload["interpretation"] = "loss_realization"
        else:
            event.payload["interpretation"] = "neutral"

    return event


def parse_bitview_nupl(data: dict[str, Any]) -> StandardEvent:
    """Parse NUPL data with zone classification.

    Note: Bitview NUPL is scaled by 100 (e.g., 19.94 means 0.1994).

    Args:
        data: Raw NUPL data from client

    Returns:
        StandardEvent with NUPL data and zone classification
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # Bitview NUPL is scaled by 100, so we need to divide
        normalized_value = value / 100.0 if abs(value) > 1 else value

        # Store both raw and normalized values
        event.payload["value_normalized"] = normalized_value

        # Determine zone based on normalized value
        if normalized_value < 0:
            event.payload["zone"] = "capitulation"
        elif normalized_value < 0.25:
            event.payload["zone"] = "hope-fear"
        elif normalized_value < 0.5:
            event.payload["zone"] = "optimism"
        elif normalized_value < 0.75:
            event.payload["zone"] = "belief"
        else:
            event.payload["zone"] = "euphoria"

    return event


def parse_bitview_mvrv(data: dict[str, Any]) -> StandardEvent:
    """Parse MVRV data with signal.

    Args:
        data: Raw MVRV data from client

    Returns:
        StandardEvent with MVRV data and signal
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # MVRV interpretation
        if value < 1.0:
            event.payload["signal"] = "undervalued"
        elif value > 3.5:
            event.payload["signal"] = "overvalued"
        else:
            event.payload["signal"] = "neutral"

    return event


def parse_bitview_liveliness(data: dict[str, Any]) -> StandardEvent:
    """Parse Liveliness data.

    Liveliness = 1 - (cumulative CDD / cumulative coin days)
    It measures network activity and can substitute for dormancy.

    Args:
        data: Raw Liveliness data from client

    Returns:
        StandardEvent with Liveliness data
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # Liveliness interpretation
        # Higher = more active network (coins moving more frequently)
        # Lower = more HODLing
        if value > 0.7:
            event.payload["signal"] = "high_activity"
        elif value < 0.5:
            event.payload["signal"] = "strong_hodl"
        else:
            event.payload["signal"] = "normal"

    return event


def parse_bitview_realized_cap(data: dict[str, Any]) -> StandardEvent:
    """Parse Realized Cap data.

    Args:
        data: Raw Realized Cap data from client

    Returns:
        StandardEvent with Realized Cap data
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # Convert to billions for readability
        event.payload["value_billions"] = value / 1e9

    return event


def parse_bitview_realized_price(data: dict[str, Any]) -> StandardEvent:
    """Parse Realized Price data.

    Args:
        data: Raw Realized Price data from client

    Returns:
        StandardEvent with Realized Price data
    """
    event = parse_bitview_metric(data)
    return event


def parse_bitview_puell(data: dict[str, Any]) -> StandardEvent:
    """Parse Puell Multiple data.

    Args:
        data: Raw Puell Multiple data from client

    Returns:
        StandardEvent with Puell Multiple data
    """
    event = parse_bitview_metric(data)

    value = event.payload.get("value")
    if value is not None:
        # Puell interpretation
        if value < 0.5:
            event.payload["signal"] = "miner_stress"  # Potential bottom
        elif value > 2.0:
            event.payload["signal"] = "high_profitability"  # Potential top
        else:
            event.payload["signal"] = "normal"

    return event


def validate_bitview_data(data: dict[str, Any]) -> None:
    """Validate Bitview data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    if "metric_name" not in data:
        raise ValueError("Data must contain 'metric_name'")

    values = data.get("values", [])
    if not values:
        # Allow empty data but log warning
        return
