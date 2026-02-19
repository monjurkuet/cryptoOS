# src/market_scraper/connectors/blockchain_info/parsers.py

"""Response parsers for Blockchain.info data."""

from datetime import datetime, timezone
from typing import Any

from market_scraper.connectors.blockchain_info.config import BlockchainChartType
from market_scraper.core.events import StandardEvent


def parse_chart_response(
    data: dict[str, Any],
    chart_type: BlockchainChartType,
    source: str = "blockchain_info",
) -> StandardEvent:
    """Parse Blockchain.info chart response into a StandardEvent.

    Args:
        data: Raw API response from Blockchain.info chart endpoint
        chart_type: Type of chart being parsed
        source: Source identifier for the event

    Returns:
        Standardized event containing chart data

    Raises:
        ValueError: If required fields are missing or invalid
    """
    if data.get("status") != "ok":
        error_msg = data.get("error", "Unknown error")
        raise ValueError(f"Chart API returned error: {error_msg}")

    values = data.get("values", [])
    if not values:
        raise ValueError(f"No values in chart response for {chart_type.value}")

    # Get the most recent value
    latest = values[-1] if values else None
    if latest is None:
        raise ValueError(f"No values in chart response for {chart_type.value}")

    timestamp = datetime.fromtimestamp(latest["x"], tz=timezone.utc)
    value = latest["y"]

    # Calculate change from previous period if available
    previous = values[-2] if len(values) > 1 else None
    change_24h = None
    if previous:
        try:
            change_24h = ((value - previous["y"]) / previous["y"]) * 100
        except (TypeError, ZeroDivisionError):
            pass

    return StandardEvent.create(
        event_type="blockchain_chart",
        source=source,
        payload={
            "chart_type": chart_type.value,
            "name": data.get("name", chart_type.value),
            "unit": data.get("unit"),
            "period": data.get("period"),
            "description": data.get("description"),
            "timestamp": timestamp.isoformat(),
            "value": value,
            "change_24h_percent": change_24h,
            "values_count": len(values),
        },
    )


def parse_chart_historical(
    data: dict[str, Any],
    chart_type: BlockchainChartType,
    source: str = "blockchain_info",
) -> list[StandardEvent]:
    """Parse Blockchain.info chart response into a list of historical StandardEvents.

    Args:
        data: Raw API response from Blockchain.info chart endpoint
        chart_type: Type of chart being parsed
        source: Source identifier for the events

    Returns:
        List of standardized events, one per data point
    """
    if data.get("status") != "ok":
        return []

    values = data.get("values", [])
    events = []

    for point in values:
        try:
            timestamp = datetime.fromtimestamp(point["x"], tz=timezone.utc)
            event = StandardEvent.create(
                event_type="blockchain_chart_historical",
                source=source,
                payload={
                    "chart_type": chart_type.value,
                    "timestamp": timestamp.isoformat(),
                    "value": point["y"],
                },
            )
            events.append(event)
        except (KeyError, TypeError, OSError):
            continue

    return events


def parse_simple_query_response(
    value: str | int | float,
    metric_name: str,
    source: str = "blockchain_info",
) -> StandardEvent:
    """Parse simple query response into a StandardEvent.

    Args:
        value: Raw response value from simple query API
        metric_name: Name of the metric (e.g., 'hashrate', 'difficulty')
        source: Source identifier for the event

    Returns:
        Standardized event containing the metric value
    """
    return StandardEvent.create(
        event_type="blockchain_metric",
        source=source,
        payload={
            "metric_name": metric_name,
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def parse_all_charts_response(
    charts_data: dict[str, dict[str, Any]],
    source: str = "blockchain_info",
) -> StandardEvent:
    """Parse all charts data into a single aggregated StandardEvent.

    Args:
        charts_data: Dictionary mapping chart names to their data
        source: Source identifier for the event

    Returns:
        Standardized event containing all chart data
    """
    metrics = {}
    latest_timestamp = None

    for chart_name, data in charts_data.items():
        if data.get("status") != "ok":
            continue

        values = data.get("values", [])
        if not values:
            continue

        latest = values[-1]
        timestamp = datetime.fromtimestamp(latest["x"], tz=timezone.utc)

        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp

        metrics[chart_name] = {
            "value": latest["y"],
            "unit": data.get("unit"),
            "name": data.get("name"),
        }

    return StandardEvent.create(
        event_type="blockchain_network_summary",
        source=source,
        payload={
            "timestamp": latest_timestamp.isoformat() if latest_timestamp else None,
            "metrics": metrics,
            "charts_fetched": len(metrics),
        },
    )


def parse_current_metrics(
    metrics: dict[str, Any],
    source: str = "blockchain_info",
) -> StandardEvent:
    """Parse current metrics from simple query API into a StandardEvent.

    Args:
        metrics: Dictionary of metric names to values
        source: Source identifier for the event

    Returns:
        Standardized event containing current network metrics
    """
    # Convert satoshis to BTC for total_btc
    if metrics.get("total_btc") is not None:
        metrics["total_btc"] = metrics["total_btc"] / 100_000_000

    return StandardEvent.create(
        event_type="blockchain_current_metrics",
        source=source,
        payload={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hash_rate_ghs": metrics.get("hash_rate"),
            "difficulty": metrics.get("difficulty"),
            "block_height": metrics.get("block_count"),
            "total_btc": metrics.get("total_btc"),
            "tx_count_24h": metrics.get("tx_count_24h"),
        },
    )


def validate_chart_data(data: dict[str, Any]) -> None:
    """Validate Blockchain.info chart data structure.

    Args:
        data: Data to validate

    Raises:
        ValueError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValueError("Chart data must be a dictionary")

    if data.get("status") != "ok":
        raise ValueError(f"Chart API returned status: {data.get('status')}")

    values = data.get("values")
    if values is None:
        raise ValueError("Chart data missing 'values' field")

    if not isinstance(values, list):
        raise ValueError("'values' field must be a list")

    # Validate at least first and last entries
    if len(values) > 0:
        for point in [values[0], values[-1]]:
            if not isinstance(point, dict):
                raise ValueError(f"Invalid value point: {point}")
            if "x" not in point or "y" not in point:
                raise ValueError(f"Value point missing x or y: {point}")


def get_chart_description(chart_type: BlockchainChartType) -> str:
    """Get human-readable description for a chart type.

    Args:
        chart_type: Chart type enum value

    Returns:
        Description string
    """
    descriptions = {
        BlockchainChartType.HASH_RATE: "Network hash rate in TH/s",
        BlockchainChartType.DIFFICULTY: "Mining difficulty",
        BlockchainChartType.N_TRANSACTIONS: "Confirmed transactions per day",
        BlockchainChartType.N_UNIQUE_ADDRESSES: "Unique addresses used per day",
        BlockchainChartType.MARKET_PRICE: "Bitcoin price in USD",
        BlockchainChartType.MARKET_CAP: "Market capitalization in USD",
        BlockchainChartType.TOTAL_BITCOINS: "Total BTC in circulation",
        BlockchainChartType.MEMPOOL_COUNT: "Transactions waiting in mempool",
        BlockchainChartType.MEMPOOL_SIZE: "Mempool size in bytes",
        BlockchainChartType.ESTIMATED_TRANSACTION_VOLUME_USD: "Estimated transaction volume in USD",
        BlockchainChartType.TRADE_VOLUME_USD: "Trade volume in USD",
    }
    return descriptions.get(chart_type, f"Bitcoin metric: {chart_type.value}")
