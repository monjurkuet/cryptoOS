"""Trades markdown parser."""

import re

from trading_watchlist.models.trades import Position, PositionTarget
from trading_watchlist.parser.common import clean_text, extract_table_rows, parse_current_prices


SECTION_PATTERN = re.compile(
    r"### (?P<title>[^\n]+)\n\n(?P<body>.*?)(?=\n---\n|\n## |\Z)",
    re.DOTALL,
)


def _parse_field_tables(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in extract_table_rows(body):
        if len(row) == 2 and row[0].lower() != "field":
            fields[row[0]] = row[1]
    return fields


def _parse_targets(body: str) -> list[PositionTarget]:
    targets: list[PositionTarget] = []
    for row in extract_table_rows(body):
        if len(row) == 4 and row[0].lower() != "target":
            targets.append(
                PositionTarget(label=row[0], price_text=row[1], status=row[2], notes=row[3])
            )
        elif len(row) == 3 and row[0].lower() != "target":
            targets.append(PositionTarget(label=row[0], price_text=row[1], notes=row[2]))
    return targets


def parse_positions(markdown: str) -> tuple[dict[str, float], list[Position]]:
    """Parse open and pending positions."""

    prices = parse_current_prices(markdown)
    positions: list[Position] = []
    current_section = ""

    for chunk in markdown.splitlines():
        if chunk.startswith("## "):
            current_section = clean_text(chunk.removeprefix("## "))

    for match in SECTION_PATTERN.finditer(markdown):
        title = clean_text(match.group("title"))
        body = match.group("body")
        fields = _parse_field_tables(body)
        if "Rule ID" not in fields:
            continue
        positions.append(
            Position(
                title=title,
                rule_id=fields["Rule ID"],
                section="pending" if "Pending / IN PLAY" in markdown[: match.start()] else "open",
                direction=fields.get("Direction"),
                asset=fields.get("Asset"),
                status=fields.get("Status"),
                fields=fields,
                targets=_parse_targets(body),
            )
        )

    return prices, positions
