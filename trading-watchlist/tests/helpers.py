from pathlib import Path


def write_markdown_dataset(base_dir: Path) -> None:
    (base_dir / "analysis-rules.md").write_text(
        """
> **Current prices:** BTC: **$66,596** | ETH: **$1,991**

### RULE: EXPORT-20260330-BTC-01

- **Asset:** BTC
- **Timeframe:** DAILY
- **Direction:** SHORT
- **Condition:** IF BTC weakens THEN lower
- **Entry:** Below $66,000
- **Targets:**
  1. $63,000
- **Invalidation:** Above $68,000
- **Confidence:** HIGH
- **Status:** ACTIVE
""",
        encoding="utf-8",
    )
    (base_dir / "analysis-trades.md").write_text(
        """
> **Current prices:** BTC: **$66,596**

## Open Positions

### #1 - Export Position

| Field | Value |
|-------|-------|
| **Rule ID** | EXPORT-20260330-BTC-01 |
| **Direction** | SHORT |
| **Asset** | BTC |
""",
        encoding="utf-8",
    )
    (base_dir / "analysis-watchlist.md").write_text(
        """
> **Current prices:** BTC: **$66,596** | ETH: **$1,991**

## 🟡 Approaching Setups

### 1. Export Setup

BTC is close.

| Field | Value |
|-------|-------|
| **Rule ID** | EXPORT-20260330-BTC-01 |
| **Asset** | BTC |

---

## 📊 Price Alert Levels

| Price | Asset | Direction | What It Triggers | Priority |
|-------|-------|-----------|------------------|----------|
| **$65,000** | BTC | ↓ Break | Support loss | 🔴 CRITICAL |
| **$1,930** | ETH | ↓ Support | Retest | 🟠 MEDIUM |
""",
        encoding="utf-8",
    )
