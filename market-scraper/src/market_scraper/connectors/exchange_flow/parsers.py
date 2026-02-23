# src/market_scraper/connectors/exchange_flow/parsers.py

"""Parsers for exchange flow data."""

from typing import Any

from market_scraper.core.events import StandardEvent


def parse_exchange_flow_data(data: dict[str, Any], source: str = "exchange_flow") -> StandardEvent:
    """Parse exchange flow data into StandardEvent.

    Args:
        data: Raw flow data from client
        source: Source identifier

    Returns:
        StandardEvent with exchange flow data
    """

    # Find latest non-null values
    def get_latest(values: list) -> float | None:
        for i in range(len(values) - 1, -1, -1):
            if values[i] is not None:
                return values[i]
        return None

    latest_date = data["dates"][-1] if data["dates"] else None
    flow_in = get_latest(data.get("flow_in_btc", []))
    flow_out = get_latest(data.get("flow_out_btc", []))
    netflow = get_latest(data.get("netflow_btc", []))
    supply = get_latest(data.get("supply_btc", []))

    # Build historical data (last 365 days)
    historical = []
    for i in range(max(0, len(data["dates"]) - 365), len(data["dates"])):
        historical.append(
            {
                "date": data["dates"][i],
                "flow_in_btc": data["flow_in_btc"][i],
                "flow_out_btc": data["flow_out_btc"][i],
                "netflow_btc": data["netflow_btc"][i],
                "supply_btc": data["supply_btc"][i],
            }
        )

    # Calculate statistics
    valid_netflow = [v for v in data.get("netflow_btc", []) if v is not None]
    stats = {}
    if valid_netflow:
        stats = {
            "netflow_7d_avg": sum(valid_netflow[-7:]) / len(valid_netflow[-7:])
            if len(valid_netflow) >= 7
            else None,
            "netflow_30d_avg": sum(valid_netflow[-30:]) / len(valid_netflow[-30:])
            if len(valid_netflow) >= 30
            else None,
        }

    return StandardEvent.create(
        source=source,
        event_type="exchange_flow",
        payload={
            "date": latest_date,
            "flow_in_btc": flow_in,
            "flow_out_btc": flow_out,
            "netflow_btc": netflow,
            "supply_btc": supply,
            "statistics": stats,
            "historical": historical,
        },
    )


def parse_exchange_flow_summary(data: dict[str, Any]) -> StandardEvent:
    """Parse exchange flow data into a summary.

    Args:
        data: Raw flow data from client

    Returns:
        StandardEvent with summary and interpretation
    """
    event = parse_exchange_flow_data(data)

    # Add interpretation
    netflow = event.payload.get("netflow_btc")
    event.payload.get("supply_btc")
    stats = event.payload.get("statistics", {})

    if netflow is not None:
        if netflow > 0:
            event.payload["netflow_interpretation"] = "bullish"  # BTC leaving exchanges
        else:
            event.payload["netflow_interpretation"] = "bearish"  # BTC entering exchanges

    # Compare to 7-day average
    avg_7d = stats.get("netflow_7d_avg")
    if netflow is not None and avg_7d is not None:
        if netflow > avg_7d * 1.5:
            event.payload["trend"] = "strong_outflow"
        elif netflow < avg_7d * 0.5:
            event.payload["trend"] = "strong_inflow"
        else:
            event.payload["trend"] = "normal"

    return event


def validate_exchange_flow_data(data: dict[str, Any]) -> None:
    """Validate exchange flow data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    required_keys = ["dates", "flow_in_btc", "flow_out_btc", "netflow_btc", "supply_btc"]
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Data must contain '{key}'")

    if not data["dates"]:
        raise ValueError("Data must contain at least one data point")
