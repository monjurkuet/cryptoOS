from trading_watchlist.parser.common import parse_price_range
from trading_watchlist.parser.rules import parse_rules
from trading_watchlist.parser.trades import parse_positions
from trading_watchlist.parser.watchlist import parse_watchlist


def test_parse_rules_extracts_btc_rule_and_prices() -> None:
    markdown = """
> **Current prices:** BTC: **$66,596** | ETH: **$1,991**

### RULE: TEST-20260329-BTC-01

- **Asset:** BTC
- **Timeframe:** DAILY
- **Direction:** SHORT
- **Condition:** IF BTC daily close < $70,000 THEN continuation lower
- **Entry:** Below $70,000 on confirmed daily close
- **Targets:**
  1. $63,000
  2. $55,000-$58,000
- **Invalidation:** BTC reclaims and holds above $76,000
- **Confidence:** HIGH
- **Status:** ACTIVE
"""
    prices, rules = parse_rules(markdown)

    assert prices["BTC"] == 66596.0
    assert len(rules) == 1
    assert rules[0].rule_id == "TEST-20260329-BTC-01"
    assert rules[0].targets[0].min_price == 63000.0


def test_parse_rules_ignores_annotation_numbers_in_targets() -> None:
    markdown = """
### RULE: TEST-20260329-BTC-ANNOTATION

- **Asset:** BTC
- **Direction:** SHORT
- **Targets:**
  1. $66,250 (7% moon cycle avg downside)
  2. $63,000 (monthly 55 EMA)
- **Status:** ACTIVE
"""
    _, rules = parse_rules(markdown)

    assert rules[0].targets[0].min_price == 66250.0
    assert rules[0].targets[0].max_price == 66250.0
    assert rules[0].targets[1].min_price == 63000.0
    assert rules[0].targets[1].max_price == 63000.0


def test_parse_price_range_supports_true_ranges_and_index_values() -> None:
    assert parse_price_range("$55,000-$58,000") == (55000.0, 58000.0)
    assert parse_price_range("$65K–$65,571") == (65000.0, 65571.0)
    assert parse_price_range("~6,250 (SPY futures)") == (6250.0, 6250.0)


def test_parse_positions_extracts_open_and_pending_sections() -> None:
    markdown = """
> **Current prices:** BTC: **$66,596**

## Open Positions

### #1 - Sample Open

| Field | Value |
|-------|-------|
| **Rule ID** | TEST-OPEN |
| **Direction** | SHORT |
| **Asset** | BTC |

| Target | Price | Status | Notes |
|--------|-------|--------|-------|
| TP1 | $63,000 | Active | Near |

---

## Pending / IN PLAY (Not Yet Entered)

### #2 - Sample Pending

| Field | Value |
|-------|-------|
| **Rule ID** | TEST-PENDING |
| **Direction** | LONG |
| **Asset** | BTC |
"""
    _, positions = parse_positions(markdown)

    assert [position.rule_id for position in positions] == ["TEST-OPEN", "TEST-PENDING"]
    assert positions[0].targets[0].label == "TP1"
    assert positions[1].section == "pending"


def test_parse_watchlist_extracts_approaching_and_alerts() -> None:
    markdown = """
> **Current prices:** BTC: **$66,596** | SPX: **6,368.86**

## 🟡 Approaching Setups

### 1. BTC Retest

BTC is near the zone.

| Field | Value |
|-------|-------|
| **Rule ID** | TEST-APPROACH |
| **Entry** | $65,000-$65,500 |

---

## 📊 Price Alert Levels

| Price | Asset | Direction | What It Triggers | Priority |
|-------|-------|-----------|------------------|----------|
| **$65,000** | BTC | ↓ Break | VAL break | 🔴 CRITICAL |
"""
    prices, watchlist = parse_watchlist(markdown)

    assert prices["SPX"] == 6368.86
    assert watchlist.approaching[0].rule_id == "TEST-APPROACH"
    assert watchlist.alerts[0].asset == "BTC"
