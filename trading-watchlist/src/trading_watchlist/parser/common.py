"""Shared parser helpers."""

import re


PRICE_PATTERN = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?)")
LEADING_PRICE_RANGE_PATTERN = re.compile(
    r"^\s*~?\$?\s*"
    r"(?P<first>[0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]+(?:\.\d+)?)"
    r"(?P<first_suffix>[Kk]?)"
    r"(?:\s*[–-]\s*~?\$?\s*"
    r"(?P<second>[0-9]{1,3}(?:,[0-9]{3})*(?:\.\d+)?|[0-9]+(?:\.\d+)?)"
    r"(?P<second_suffix>[Kk]?))?"
)


def clean_text(value: str) -> str:
    """Strip markdown markers and surrounding whitespace."""

    cleaned = value.replace("**", "").replace("`", "").replace("~~", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_float(value: str) -> float | None:
    """Parse a number from free-form text."""

    match = PRICE_PATTERN.search(value)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def parse_price_range(value: str) -> tuple[float | None, float | None]:
    """Parse a single price or range from text."""

    match = LEADING_PRICE_RANGE_PATTERN.match(value)
    if not match:
        return None, None

    def _normalize(number: str, suffix: str) -> float:
        parsed = float(number.replace(",", ""))
        return parsed * 1000 if suffix.upper() == "K" else parsed

    first = _normalize(match.group("first"), match.group("first_suffix"))
    second = match.group("second")
    if second is None:
        return first, first

    second_value = _normalize(second, match.group("second_suffix"))
    return min(first, second_value), max(first, second_value)


def parse_current_prices(markdown: str) -> dict[str, float]:
    """Parse the metadata current prices line."""

    match = re.search(r"\*\*Current prices:\*\*(.+)", markdown)
    if not match:
        return {}

    prices: dict[str, float] = {}
    for segment in match.group(1).split("|"):
        if ":" not in segment:
            continue
        asset, raw_value = segment.split(":", 1)
        price = parse_float(raw_value)
        if price is not None:
            prices[asset.strip().upper()] = price
    return prices


def extract_table_rows(section: str) -> list[list[str]]:
    """Extract markdown table rows without separator rows."""

    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(" ", "")) == set():
            continue
        parts = [clean_text(part) for part in stripped.strip("|").split("|")]
        rows.append(parts)
    return rows
