"""Rules markdown parser."""

import re

from trading_watchlist.models.rules import Rule, RuleTarget
from trading_watchlist.parser.common import clean_text, parse_current_prices, parse_price_range


RULE_BLOCK_PATTERN = re.compile(
    r"### RULE: (?P<rule_id>[^\n]+)\n\n(?P<body>.*?)(?=\n---\n|\n## |\Z)",
    re.DOTALL,
)


def _extract_field(body: str, field_name: str) -> str | None:
    pattern = rf"^- \*\*{re.escape(field_name)}:\*\*\s*(.+)$"
    match = re.search(pattern, body, re.MULTILINE)
    return clean_text(match.group(1)) if match else None


def _extract_targets(body: str) -> list[RuleTarget]:
    match = re.search(r"^- \*\*Targets:\*\*\n(?P<targets>(?:  \d+\..*\n)+)", body, re.MULTILINE)
    if not match:
        return []

    targets: list[RuleTarget] = []
    for line in match.group("targets").splitlines():
        target_match = re.match(r"\s*(\d+)\.\s*(.+)$", line)
        if not target_match:
            continue
        raw = clean_text(target_match.group(2))
        min_price, max_price = parse_price_range(raw)
        status = "HIT" if "HIT" in raw.upper() else None
        targets.append(
            RuleTarget(
                label=f"TP{target_match.group(1)}",
                value_text=raw,
                min_price=min_price,
                max_price=max_price,
                status=status,
            )
        )
    return targets


def parse_rules(markdown: str) -> tuple[dict[str, float], list[Rule]]:
    """Parse metadata prices and rule blocks."""

    prices = parse_current_prices(markdown)
    rules: list[Rule] = []

    for match in RULE_BLOCK_PATTERN.finditer(markdown):
        rule_id = clean_text(match.group("rule_id")).replace(" (UPDATED)", "")
        body = match.group("body")
        rules.append(
            Rule(
                rule_id=rule_id,
                asset=_extract_field(body, "Asset") or "UNKNOWN",
                timeframe=_extract_field(body, "Timeframe"),
                direction=_extract_field(body, "Direction") or "UNKNOWN",
                condition=_extract_field(body, "Condition"),
                entry=_extract_field(body, "Entry"),
                targets=_extract_targets(body),
                invalidation=_extract_field(body, "Invalidation"),
                confidence=_extract_field(body, "Confidence"),
                source=_extract_field(body, "Source"),
                video_date=_extract_field(body, "Video Date"),
                status=_extract_field(body, "Status") or "UNKNOWN",
                valid_until=_extract_field(body, "Valid Until"),
                last_checked=_extract_field(body, "Last Checked"),
                notes=_extract_field(body, "Notes"),
            )
        )

    return prices, rules
