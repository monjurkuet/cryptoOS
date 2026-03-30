"""Watchlist markdown parser."""

import re

from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.parser.common import clean_text, extract_table_rows, parse_current_prices


def _extract_section(markdown: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\n\n(?P<body>.*?)(?=\n---\n|\n## |\Z)"
    match = re.search(pattern, markdown, re.DOTALL)
    return match.group("body") if match else ""


def _extract_subsections(section: str) -> list[tuple[str, str]]:
    return [
        (clean_text(match.group("title")), match.group("body"))
        for match in re.finditer(
            r"### (?P<title>[^\n]+)\n\n(?P<body>.*?)(?=\n### |\Z)", section, re.DOTALL
        )
    ]


def _extract_rule_id(section: str) -> str | None:
    match = re.search(r"\*\*Rule ID\*\*\s*\|\s*([^|\n]+)", section)
    return clean_text(match.group(1)) if match else None


def parse_watchlist(markdown: str) -> tuple[dict[str, float], WatchlistSummary]:
    """Parse watchlist summary data."""

    prices = parse_current_prices(markdown)

    live_positions_section = _extract_section(markdown, "🔴 Live Positions")
    live_positions = [
        {
            "id": row[0],
            "entry": row[1],
            "pnl": row[2],
            "target_1": row[3],
            "target_2": row[4],
            "status": row[5],
        }
        for row in extract_table_rows(live_positions_section)
        if len(row) == 6 and row[0] != "ID"
    ]

    approaching_section = _extract_section(markdown, "🟡 Approaching Setups")
    approaching = []
    for title, body in _extract_subsections(approaching_section):
        fields = {
            row[0]: row[1]
            for row in extract_table_rows(body)
            if len(row) == 2 and row[0] != "Field"
        }
        summary_line = next(
            (
                clean_text(line)
                for line in body.splitlines()
                if line and not line.startswith("|") and not line.startswith(">")
            ),
            None,
        )
        approaching.append(
            ApproachingSetup(
                title=title, rule_id=fields.get("Rule ID"), fields=fields, summary=summary_line
            )
        )

    future_section = _extract_section(markdown, "🟢 Conditional Future Setups")
    future_setups = []
    for title, body in _extract_subsections(future_section):
        fields = {
            row[0]: row[1]
            for row in extract_table_rows(body)
            if len(row) == 2 and row[0] != "Field"
        }
        future_setups.append(
            ApproachingSetup(title=title, rule_id=fields.get("Rule ID"), fields=fields)
        )

    alerts_section = _extract_section(markdown, "📊 Price Alert Levels")
    alerts = [
        AlertLevel(price=row[0], asset=row[1], direction=row[2], trigger=row[3], priority=row[4])
        for row in extract_table_rows(alerts_section)
        if len(row) == 5 and row[0] != "Price"
    ]

    expiring_section = _extract_section(markdown, "⏰ Expiring Soon")
    expiring = [
        {
            "rule_id": row[0],
            "video_date": row[1],
            "expires": row[2],
            "days_left": row[3],
            "action": row[4],
        }
        for row in extract_table_rows(expiring_section)
        if len(row) == 5 and row[0] != "Rule ID"
    ]

    return prices, WatchlistSummary(
        live_positions=live_positions,
        approaching=approaching,
        future_setups=future_setups,
        alerts=alerts,
        expiring=expiring,
    )
