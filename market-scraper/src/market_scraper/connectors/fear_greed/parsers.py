# src/market_scraper/connectors/fear_greed/parsers.py

"""Response parsers for Fear & Greed Index data."""

from datetime import datetime, timezone
from typing import Any

from market_scraper.core.events import StandardEvent


def parse_fear_greed_response(
    data: dict[str, Any],
    source: str = "fear_greed",
) -> StandardEvent:
    """Parse Fear & Greed Index response into a StandardEvent.

    Args:
        data: Raw API response from Fear & Greed endpoint
        source: Source identifier for the event

    Returns:
        Standardized event containing Fear & Greed data

    Raises:
        ValueError: If required fields are missing or invalid
    """
    if data.get("metadata", {}).get("error"):
        raise ValueError(f"API returned error: {data['metadata']['error']}")

    fng_data = data.get("data", [])
    if not fng_data:
        raise ValueError("No Fear & Greed data in response")

    # Get latest entry
    latest = fng_data[0]
    value = int(latest.get("value", 0))
    classification = latest.get("value_classification", "Unknown")
    timestamp = datetime.fromtimestamp(int(latest["timestamp"]), tz=timezone.utc)

    # Get previous value for comparison
    previous_value = None
    change = None
    if len(fng_data) > 1:
        previous_value = int(fng_data[1].get("value", 0))
        change = value - previous_value

    return StandardEvent.create(
        event_type="fear_greed_index",
        source=source,
        payload={
            "timestamp": timestamp.isoformat(),
            "value": value,
            "classification": classification,
            "sentiment": _get_sentiment(value),
            "previous_value": previous_value,
            "change": change,
            "time_until_update": latest.get("time_until_update"),
        },
    )


def parse_fear_greed_historical(
    data: dict[str, Any],
    source: str = "fear_greed",
) -> list[StandardEvent]:
    """Parse Fear & Greed historical data into a list of StandardEvents.

    Args:
        data: Raw API response from Fear & Greed endpoint
        source: Source identifier for the events

    Returns:
        List of standardized events, one per data point
    """
    fng_data = data.get("data", [])
    events = []

    for entry in fng_data:
        try:
            timestamp = datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc)
            value = int(entry.get("value", 0))

            event = StandardEvent.create(
                event_type="fear_greed_historical",
                source=source,
                payload={
                    "timestamp": timestamp.isoformat(),
                    "value": value,
                    "classification": entry.get("value_classification"),
                    "sentiment": _get_sentiment(value),
                },
            )
            events.append(event)
        except (KeyError, TypeError, OSError, ValueError):
            continue

    return events


def parse_fear_greed_summary(
    data: dict[str, Any],
    source: str = "fear_greed",
) -> StandardEvent:
    """Parse Fear & Greed data into a summary StandardEvent.

    Args:
        data: Raw API response from Fear & Greed endpoint
        source: Source identifier for the event

    Returns:
        Standardized event containing summary data
    """
    if data.get("metadata", {}).get("error"):
        raise ValueError(f"API returned error: {data['metadata']['error']}")

    fng_data = data.get("data", [])
    if not fng_data:
        raise ValueError("No Fear & Greed data in response")

    # Calculate statistics
    values = [int(entry.get("value", 0)) for entry in fng_data]

    summary = {
        "current": {
            "value": values[0] if values else None,
            "classification": fng_data[0].get("value_classification") if fng_data else None,
            "timestamp": datetime.fromtimestamp(
                int(fng_data[0]["timestamp"]), tz=timezone.utc
            ).isoformat()
            if fng_data
            else None,
        },
        "statistics": {
            "count": len(values),
            "average": sum(values) / len(values) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        },
        "distribution": _calculate_distribution(values),
        "trend": _calculate_trend(values[:7]) if len(values) >= 7 else None,
    }

    return StandardEvent.create(
        event_type="fear_greed_summary",
        source=source,
        payload=summary,
    )


def validate_fear_greed_data(data: dict[str, Any]) -> None:
    """Validate Fear & Greed data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Fear & Greed data must be a dictionary")

    if data.get("metadata", {}).get("error"):
        raise ValueError(f"API error: {data['metadata']['error']}")

    fng_data = data.get("data")
    if fng_data is None:
        raise ValueError("Fear & Greed data missing 'data' field")

    if not isinstance(fng_data, list):
        raise ValueError("'data' field must be a list")

    if len(fng_data) == 0:
        raise ValueError("'data' field is empty")

    # Validate first entry
    first = fng_data[0]
    required_fields = ["value", "value_classification", "timestamp"]
    for field in required_fields:
        if field not in first:
            raise ValueError(f"Missing required field: {field}")

    # Validate value is in range
    try:
        value = int(first["value"])
        if not 0 <= value <= 100:
            raise ValueError(f"Value out of range: {value}")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid value: {first['value']}") from e


def _get_sentiment(value: int) -> str:
    """Get sentiment category from value.

    Args:
        value: Fear & Greed value (0-100)

    Returns:
        Sentiment category string
    """
    if value <= 20:
        return "extreme_fear"
    elif value <= 40:
        return "fear"
    elif value <= 60:
        return "neutral"
    elif value <= 80:
        return "greed"
    else:
        return "extreme_greed"


def _calculate_distribution(values: list[int]) -> dict[str, int]:
    """Calculate distribution of sentiment categories.

    Args:
        values: List of Fear & Greed values

    Returns:
        Dictionary with count per category
    """
    distribution = {
        "extreme_fear": 0,
        "fear": 0,
        "neutral": 0,
        "greed": 0,
        "extreme_greed": 0,
    }

    for value in values:
        sentiment = _get_sentiment(value)
        distribution[sentiment] += 1

    return distribution


def _calculate_trend(values: list[int]) -> str:
    """Calculate trend direction from recent values.

    Args:
        values: List of recent Fear & Greed values (oldest first)

    Returns:
        Trend direction string ('improving', 'declining', 'stable')
    """
    if len(values) < 2:
        return "insufficient_data"

    first_half_avg = sum(values[: len(values) // 2]) / (len(values) // 2)
    second_half_avg = sum(values[len(values) // 2 :]) / (len(values) - len(values) // 2)

    diff = second_half_avg - first_half_avg

    if diff > 5:
        return "improving"  # Moving toward greed
    elif diff < -5:
        return "declining"  # Moving toward fear
    else:
        return "stable"
