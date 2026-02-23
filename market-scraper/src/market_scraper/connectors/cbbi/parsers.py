# src/market_scraper/connectors/cbbi/parsers.py

"""Response parsers for CBBI data."""

from datetime import datetime
from typing import Any

from market_scraper.core.events import StandardEvent


def parse_cbbi_index_response(data: dict[str, Any], source: str = "cbbi") -> StandardEvent:
    """Parse CBBI index response into a StandardEvent.

    Args:
        data: Raw API response from CBBI endpoint
        source: Source identifier for the event

    Returns:
        Standardized event containing CBBI index data

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # CBBI API uses "Confidence" field for the main index
    cbbi_data = data.get("Confidence", data.get("CBBI", {}))

    if not cbbi_data:
        raise ValueError("No CBBI data found in response")

    # Find most recent entry (highest timestamp)
    timestamps = sorted(cbbi_data.keys(), key=int, reverse=True)
    latest_ts = int(timestamps[0])
    latest_value = cbbi_data[timestamps[0]]

    # Extract components at this timestamp
    components = _extract_components(data, latest_ts)

    # Get price at this timestamp
    price_data = data.get("Price", {})
    price = price_data.get(timestamps[0])

    return StandardEvent.create(
        event_type="cbbi_index",
        source=source,
        payload={
            "timestamp": datetime.utcfromtimestamp(latest_ts).isoformat(),
            "confidence": latest_value,
            "components": components,
            "price": float(price) if price is not None else None,
        },
    )


def parse_cbbi_historical_response(
    data: dict[str, Any],
    days: int = 365,
    source: str = "cbbi",
) -> list[StandardEvent]:
    """Parse CBBI historical data response into a list of StandardEvents.

    Args:
        data: Raw API response from CBBI endpoint (full historical data)
        days: Number of days of history to return
        source: Source identifier for the events

    Returns:
        List of standardized events, one per data point
    """
    import time

    # CBBI API uses "Confidence" field for the main index
    cbbi_data = data.get("Confidence", data.get("CBBI", {}))
    if not cbbi_data:
        return []

    # Calculate cutoff time
    cutoff_time = time.time() - (days * 86400)
    events = []

    for ts_str, value in cbbi_data.items():
        try:
            ts = int(ts_str)
            if ts >= cutoff_time:
                components = _extract_components(data, ts)
                event = StandardEvent.create(
                    event_type="cbbi_historical",
                    source=source,
                    payload={
                        "timestamp": datetime.utcfromtimestamp(ts).isoformat(),
                        "confidence": value,
                        "components": components,
                    },
                )
                events.append(event)
        except (ValueError, TypeError):
            continue

    # Sort by timestamp descending (most recent first)
    events.sort(key=lambda e: e.payload.get("timestamp", ""), reverse=True)
    return events


def parse_cbbi_component_response(
    data: dict[str, Any],
    component_name: str,
    source: str = "cbbi",
) -> StandardEvent:
    """Parse CBBI component data response into a StandardEvent.

    Args:
        data: Raw component data from CBBI API
        component_name: Name of the component being parsed
        source: Source identifier for the event

    Returns:
        Standardized event containing component data

    Raises:
        ValueError: If component not found in data
    """
    component_data = data.get(component_name, {})

    if not component_data:
        raise ValueError(f"Component '{component_name}' not found in data")

    # Get latest value
    timestamps = sorted(component_data.keys(), key=int, reverse=True)
    current_value = component_data.get(timestamps[0]) if timestamps else None

    # Build historical list (last 30 days by default)
    import time

    cutoff = time.time() - (30 * 86400)
    historical = []
    for ts_str, value in component_data.items():
        try:
            ts = int(ts_str)
            if ts >= cutoff:
                historical.append(
                    {
                        "timestamp": datetime.utcfromtimestamp(ts).isoformat(),
                        "value": float(value),
                    }
                )
        except (ValueError, TypeError):
            continue

    historical.sort(key=lambda x: x["timestamp"], reverse=True)

    return StandardEvent.create(
        event_type="cbbi_component",
        source=source,
        payload={
            "component_name": component_name,
            "description": _get_component_description(component_name),
            "current_value": float(current_value) if current_value is not None else None,
            "historical": historical,
        },
    )


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse CBBI timestamp string into datetime object.

    CBBI uses Unix timestamps (seconds since epoch) as string keys.

    Args:
        timestamp_str: Timestamp string from CBBI API (Unix timestamp)

    Returns:
        Parsed datetime in UTC

    Raises:
        ValueError: If timestamp format is unrecognized
    """
    try:
        ts = int(timestamp_str)
        return datetime.utcfromtimestamp(ts)
    except (ValueError, TypeError, OSError) as e:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}") from e


def validate_cbbi_data(data: dict[str, Any]) -> None:
    """Validate CBBI data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("CBBI data must be a dictionary")

    # Check for required Confidence field (CBBI API uses "Confidence")
    cbbi_data = data.get("Confidence", data.get("CBBI"))
    if cbbi_data is None:
        raise ValueError("CBBI data missing 'Confidence' field")

    if not isinstance(cbbi_data, dict):
        raise ValueError("'Confidence' field must be a dictionary")

    # Check that CBBI data has at least one entry
    if len(cbbi_data) == 0:
        raise ValueError("'Confidence' field is empty")

    # Validate entries are numeric
    for ts_str, value in cbbi_data.items():
        try:
            int(ts_str)
            float(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid CBBI entry: {ts_str}={value}") from e


def _extract_components(data: dict[str, Any], timestamp: int) -> dict[str, float]:
    """Extract all component values at a specific timestamp.

    Args:
        data: Full CBBI data dict
        timestamp: Unix timestamp to extract values for

    Returns:
        Dict of component name -> value
    """
    components = {}
    ts_str = str(timestamp)

    # CBBI API field names (actual API uses these names)
    component_names = [
        "PiCycle",  # Pi Cycle Top
        "RUPL",  # Relative Unrealized Profit/Loss
        "RHODL",  # Realized HODL Ratio
        "Puell",  # Puell Multiple
        "2YMA",  # 2-Year Moving Average
        "MVRV",  # MVRV Z-Score
        "ReserveRisk",  # Reserve Risk
        "Woobull",  # Woobull Top Cap vs CVDD
        "Trolololo",  # Bitcoin Trolololo
    ]

    for name in component_names:
        if name in data and ts_str in data[name]:
            try:
                components[name] = float(data[name][ts_str])
            except (ValueError, TypeError):
                continue

    return components


def _get_component_description(component: str) -> str:
    """Get human-readable description for a CBBI component.

    Args:
        component: Component name

    Returns:
        Description string
    """
    # Descriptions for actual CBBI API field names
    descriptions = {
        "PiCycle": "Pi Cycle Top Indicator - Signals potential market cycle tops",
        "RUPL": "Relative Unrealized Profit/Loss - Measures overall profit/loss in market",
        "RHODL": "Realized HODL Ratio - Ratio of young vs old coins being spent",
        "Puell": "Puell Multiple - Ratio of daily coin issuance to moving average",
        "2YMA": "2-Year Moving Average Multiplier - Long-term price trend",
        "MVRV": "MVRV Z-Score - Market Value to Realized Value deviation",
        "ReserveRisk": "Reserve Risk - Confidence of long-term holders",
        "Woobull": "Woobull Top Cap vs CVDD - Market cap comparison metric",
        "Trolololo": "Bitcoin Trolololo - Historical price bands",
        "Price": "Current Bitcoin price in USD",
        "Confidence": "CBBI Confidence Score - Overall Bitcoin sentiment (0-100)",
        # Legacy aliases
        "PiCycleTop": "Pi Cycle Top Indicator - Signals potential market cycle tops",
        "TwoYearMA": "2-Year Moving Average Multiplier - Long-term price trend",
        "CBBI": "CBBI Confidence Score - Overall Bitcoin sentiment (0-100)",
    }
    return descriptions.get(component, f"CBBI component: {component}")
