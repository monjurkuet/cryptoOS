import json
from pathlib import Path

from fastapi.testclient import TestClient

from trading_watchlist.api.main import create_app
from trading_watchlist.config import get_settings
from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.rules import Rule, RuleTarget
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary


def write_markdown_dataset(base_dir: Path) -> None:
    rules_path = base_dir / "analysis-rules.md"
    trades_path = base_dir / "analysis-trades.md"
    watchlist_path = base_dir / "analysis-watchlist.md"

    rules_path.write_text(
        """
> **Current prices:** BTC: **$66,596** | SPX: **6,368.86**

### RULE: TEST-20260329-BTC-01

- **Asset:** BTC
- **Timeframe:** DAILY
- **Direction:** SHORT
- **Condition:** IF BTC below $70,000 THEN lower
- **Entry:** Below $70,000
- **Targets:**
  1. $63,000
- **Invalidation:** Above $76,000
- **Confidence:** HIGH
- **Status:** TRIGGERED - below $70,000 confirmed

---

### RULE: TEST-20260329-SPX-02

- **Asset:** SPX
- **Timeframe:** DAILY
- **Direction:** SHORT
- **Condition:** IF SPX weakens THEN lower
- **Entry:** Below 6,400
- **Targets:**
  1. 6,250
- **Invalidation:** Above 6,500
- **Confidence:** HIGH
- **Status:** ACTIVE
""",
        encoding="utf-8",
    )
    trades_path.write_text(
        """
> **Current prices:** BTC: **$66,596** | SPX: **6,368.86**

## Open Positions

### #1 - Sample Open

| Field | Value |
|-------|-------|
| **Rule ID** | TEST-20260329-BTC-01 |
| **Direction** | SHORT |
| **Asset** | BTC |

---

## Pending / IN PLAY (Not Yet Entered)

### #2 - Sample Pending

| Field | Value |
|-------|-------|
| **Rule ID** | TEST-20260329-SPX-02 |
| **Direction** | LONG |
| **Asset** | SPX |
""",
        encoding="utf-8",
    )
    watchlist_path.write_text(
        """
> **Current prices:** BTC: **$66,596** | ETH: **$1,991**

## 🟡 Approaching Setups

### 1. BTC Setup

BTC is near the zone.

| Field | Value |
|-------|-------|
| **Asset** | BTC |
| **Rule ID** | TEST-20260329-BTC-01 |

---

### 2. ETH Setup

ETH is near support.

| Field | Value |
|-------|-------|
| **Asset** | ETH |
| **Rule ID** | TEST-20260329-ETH-03 |

---

## 📊 Price Alert Levels

| Price | Asset | Direction | What It Triggers | Priority |
|-------|-------|-----------|------------------|----------|
| **$65,000** | BTC | ↓ Break | VAL break | 🔴 CRITICAL |
| **$1,930** | ETH | ↓ Support | Retest | 🟠 MEDIUM |
""",
        encoding="utf-8",
    )


def test_api_smoke_markdown_fallback(tmp_path: Path, monkeypatch) -> None:
    async def fake_fetch_btc_price(self) -> float:
        return 67001.5

    write_markdown_dataset(tmp_path)

    monkeypatch.setenv("TRADING_WATCHLIST_TRADING_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "trading_watchlist.services.market_data.MarketDataService.fetch_btc_price",
        fake_fetch_btc_price,
    )
    get_settings.cache_clear()

    client = TestClient(create_app())

    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/api/v1/rules").status_code == 200
    prices_response = client.get("/api/v1/prices")
    assert prices_response.status_code == 200
    assert prices_response.json() == {
        "prices": {"BTC": 67001.5, "SPX": 6368.86, "ETH": 1991.0},
        "sources": {"BTC": "market_api", "SPX": "trades_markdown", "ETH": "watchlist_markdown"},
    }

    filtered_rules = client.get(
        "/api/v1/rules",
        params={"asset": "btc", "status": "triggered", "direction": "short"},
    )
    assert filtered_rules.status_code == 200
    assert [rule["rule_id"] for rule in filtered_rules.json()] == ["TEST-20260329-BTC-01"]

    filtered_positions = client.get(
        "/api/v1/positions",
        params={"asset": "BTC", "section": "Open Positions", "direction": "SHORT"},
    )
    assert filtered_positions.status_code == 200
    assert [position["rule_id"] for position in filtered_positions.json()] == [
        "TEST-20260329-BTC-01"
    ]

    filtered_approaching = client.get(
        "/api/v1/approaching",
        params={"asset": "BTC", "rule_id": "test-20260329-btc-01"},
    )
    assert filtered_approaching.status_code == 200
    assert [setup["rule_id"] for setup in filtered_approaching.json()] == ["TEST-20260329-BTC-01"]

    filtered_alerts = client.get(
        "/api/v1/alerts",
        params={"asset": "BTC", "priority": "critical"},
    )
    assert filtered_alerts.status_code == 200
    assert [alert["asset"] for alert in filtered_alerts.json()] == ["BTC"]

    response = client.post("/api/v1/evaluate", json={"prices": {"BTC": 66500}})
    assert response.status_code == 200
    payload = response.json()
    assert payload["prices"]["BTC"] == 66500
    assert payload["evaluations"][0]["rule_id"] == "TEST-20260329-BTC-01"

    get_settings.cache_clear()


def test_api_state_endpoint_returns_canonical_bundle(tmp_path: Path, monkeypatch) -> None:
    write_markdown_dataset(tmp_path)

    monkeypatch.setenv("TRADING_WATCHLIST_TRADING_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    client = TestClient(create_app())

    response = client.get("/api/v1/state")
    assert response.status_code == 200

    payload = response.json()
    assert payload["schema_version"] == "v1"
    assert payload["prices"] == {"BTC": 66596.0, "SPX": 6368.86, "ETH": 1991.0}
    assert payload["metadata"]["source_mode"] == "markdown"
    assert payload["metadata"]["sources"] == {
        "BTC": "watchlist_markdown",
        "SPX": "trades_markdown",
        "ETH": "watchlist_markdown",
    }
    assert [rule["rule_id"] for rule in payload["rules"]] == [
        "TEST-20260329-BTC-01",
        "TEST-20260329-SPX-02",
    ]
    assert [position["rule_id"] for position in payload["positions"]] == [
        "TEST-20260329-BTC-01",
        "TEST-20260329-SPX-02",
    ]
    assert [setup["rule_id"] for setup in payload["watchlist"]["approaching"]] == [
        "TEST-20260329-BTC-01",
    ]
    assert [alert["asset"] for alert in payload["watchlist"]["alerts"]] == ["BTC", "ETH"]

    get_settings.cache_clear()


def test_api_prefers_json_when_available(tmp_path: Path, monkeypatch) -> None:
    async def fake_fetch_btc_price(self) -> float:
        raise RuntimeError("market unavailable")

    write_markdown_dataset(tmp_path)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "rules.json").write_text(
        json.dumps(
            {
                "prices": {"BTC": 70000.0},
                "rules": [
                    Rule(
                        rule_id="JSON-20260330-BTC-01",
                        asset="BTC",
                        timeframe="DAILY",
                        direction="LONG",
                        condition="IF BTC reclaims 70k THEN higher",
                        entry="Above 70,000",
                        targets=[
                            RuleTarget(
                                label="TP1",
                                value_text="$72,000",
                                min_price=72000.0,
                                max_price=72000.0,
                            )
                        ],
                        invalidation="Below 68,500",
                        confidence="HIGH",
                        status="ACTIVE",
                    ).model_dump(mode="json")
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (data_dir / "positions.json").write_text(
        json.dumps(
            {
                "prices": {"BTC": 70000.0},
                "positions": [
                    Position(
                        title="#1 - JSON Open",
                        rule_id="JSON-20260330-BTC-01",
                        section="open",
                        direction="LONG",
                        asset="BTC",
                        fields={"Rule ID": "JSON-20260330-BTC-01", "Asset": "BTC"},
                    ).model_dump(mode="json")
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (data_dir / "watchlist.json").write_text(
        json.dumps(
            {
                "prices": {"ETH": 2450.0},
                "watchlist": WatchlistSummary(
                    approaching=[
                        ApproachingSetup(
                            title="JSON BTC Setup",
                            rule_id="JSON-20260330-BTC-01",
                            fields={"Asset": "BTC", "Rule ID": "JSON-20260330-BTC-01"},
                            summary="JSON setup summary",
                        )
                    ],
                    alerts=[
                        AlertLevel(
                            price="$2,300",
                            asset="ETH",
                            direction="↑ Break",
                            trigger="Breakout",
                            priority="HIGH",
                        )
                    ],
                ).model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (data_dir / "prices.json").write_text(
        json.dumps(
            PriceResponse(
                prices={"BTC": 70000.0, "ETH": 2450.0},
                sources={"BTC": "prices_json", "ETH": "prices_json"},
            ).model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRADING_WATCHLIST_TRADING_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRADING_WATCHLIST_STRUCTURED_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        "trading_watchlist.services.market_data.MarketDataService.fetch_btc_price",
        fake_fetch_btc_price,
    )
    get_settings.cache_clear()

    client = TestClient(create_app())

    rules_response = client.get("/api/v1/rules")
    assert rules_response.status_code == 200
    assert [rule["rule_id"] for rule in rules_response.json()] == ["JSON-20260330-BTC-01"]

    prices_response = client.get("/api/v1/prices")
    assert prices_response.status_code == 200
    assert prices_response.json() == {
        "prices": {"BTC": 70000.0, "ETH": 2450.0},
        "sources": {"BTC": "prices_json", "ETH": "prices_json"},
    }

    get_settings.cache_clear()


def test_api_uses_state_json_when_split_files_are_absent(tmp_path: Path, monkeypatch) -> None:
    async def fake_fetch_btc_price(self) -> float:
        raise RuntimeError("market unavailable")

    write_markdown_dataset(tmp_path)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 70500.0, "ETH": 2400.0},
        rules=[
            Rule(
                rule_id="STATE-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC reclaims 70k THEN higher",
                entry="Above 70,000",
                targets=[
                    RuleTarget(
                        label="TP1",
                        value_text="$73,000",
                        min_price=73000.0,
                        max_price=73000.0,
                    )
                ],
                invalidation="Below 69,000",
                confidence="HIGH",
                status="ACTIVE",
            )
        ],
        positions=[],
        watchlist=WatchlistSummary(),
        metadata=StateBundleMetadata(
            source_mode="canonical_state",
            sources={"BTC": "state_json", "ETH": "state_json"},
        ),
    )
    (data_dir / "state.json").write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    monkeypatch.setenv("TRADING_WATCHLIST_TRADING_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TRADING_WATCHLIST_STRUCTURED_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        "trading_watchlist.services.market_data.MarketDataService.fetch_btc_price",
        fake_fetch_btc_price,
    )
    get_settings.cache_clear()

    client = TestClient(create_app())

    rules_response = client.get("/api/v1/rules")
    prices_response = client.get("/api/v1/prices")

    assert rules_response.status_code == 200
    assert [rule["rule_id"] for rule in rules_response.json()] == ["STATE-20260330-BTC-01"]
    assert prices_response.status_code == 200
    assert prices_response.json() == {
        "prices": {"BTC": 70500.0, "ETH": 2400.0},
        "sources": {"BTC": "state_json", "ETH": "state_json"},
    }

    get_settings.cache_clear()


def test_api_put_state_persists_artifacts_and_read_back(tmp_path: Path, monkeypatch) -> None:
    write_markdown_dataset(tmp_path)

    data_dir = tmp_path / "data"
    generated_dir = tmp_path / "generated"

    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 72000.0, "ETH": 2500.0},
        rules=[
            Rule(
                rule_id="WRITE-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC holds support THEN higher",
                entry="Above 71,500",
                targets=[
                    RuleTarget(
                        label="TP1",
                        value_text="$74,000",
                        min_price=74000.0,
                        max_price=74000.0,
                    )
                ],
                invalidation="Below 70,000",
                confidence="HIGH",
                status="ACTIVE",
            )
        ],
        positions=[
            Position(
                title="#1 - Written Position",
                rule_id="WRITE-20260330-BTC-01",
                section="open",
                direction="LONG",
                asset="BTC",
                fields={"Rule ID": "WRITE-20260330-BTC-01", "Asset": "BTC"},
            )
        ],
        watchlist=WatchlistSummary(
            approaching=[
                ApproachingSetup(
                    title="Written BTC Setup",
                    rule_id="WRITE-20260330-BTC-01",
                    fields={"Asset": "BTC", "Rule ID": "WRITE-20260330-BTC-01"},
                    summary="Freshly written setup",
                )
            ],
            alerts=[
                AlertLevel(
                    price="$2,450",
                    asset="ETH",
                    direction="↑ Break",
                    trigger="Breakout",
                    priority="HIGH",
                )
            ],
        ),
        metadata=StateBundleMetadata(
            source_mode="canonical_state",
            sources={"BTC": "state_json", "ETH": "state_json"},
        ),
    )

    monkeypatch.setenv("TRADING_WATCHLIST_TRADING_DATA_DIR", str(generated_dir))
    monkeypatch.setenv("TRADING_WATCHLIST_STRUCTURED_DATA_DIR", str(data_dir))
    get_settings.cache_clear()

    client = TestClient(create_app())

    write_response = client.put("/api/v1/state", json=state.model_dump(mode="json"))
    assert write_response.status_code == 200
    assert write_response.json() == {
        "schema_version": "v1",
        "source_mode": "canonical_state",
        "written_files": [
            str(data_dir / "rules.json"),
            str(data_dir / "positions.json"),
            str(data_dir / "watchlist.json"),
            str(data_dir / "prices.json"),
            str(data_dir / "state.json"),
            str(data_dir / "manifest.json"),
            str(generated_dir / "analysis-rules.generated.md"),
            str(generated_dir / "analysis-trades.generated.md"),
            str(generated_dir / "analysis-watchlist.generated.md"),
            str(generated_dir / "analysis-brief.generated.md"),
        ],
    }

    assert (
        json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))["files"]["state"][
            "filename"
        ]
        == "state.json"
    )
    assert "Written BTC Setup" in (generated_dir / "analysis-watchlist.generated.md").read_text(
        encoding="utf-8"
    )

    state_response = client.get("/api/v1/state")
    rules_response = client.get("/api/v1/rules")

    assert state_response.status_code == 200
    assert state_response.json()["rules"][0]["rule_id"] == "WRITE-20260330-BTC-01"
    assert rules_response.status_code == 200
    assert [rule["rule_id"] for rule in rules_response.json()] == ["WRITE-20260330-BTC-01"]

    get_settings.cache_clear()
