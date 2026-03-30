import json
from pathlib import Path

from trading_watchlist.models.rules import Rule, RuleTarget
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.repositories.json import JsonRepository


def test_json_repository_uses_state_as_canonical_source(tmp_path: Path) -> None:
    repository = JsonRepository(
        rules_path=tmp_path / "rules.json",
        positions_path=tmp_path / "positions.json",
        watchlist_path=tmp_path / "watchlist.json",
        prices_path=tmp_path / "prices.json",
        state_path=tmp_path / "state.json",
        manifest_path=tmp_path / "manifest.json",
    )
    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 71000.0, "SOL": 180.0},
        rules=[
            Rule(
                rule_id="STATE-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC reclaims resistance THEN higher",
                entry="Above 70,500",
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
        positions=[
            Position(
                title="#1 - State Position",
                rule_id="STATE-20260330-BTC-01",
                section="open",
                direction="LONG",
                asset="BTC",
                fields={"Rule ID": "STATE-20260330-BTC-01", "Asset": "BTC"},
            )
        ],
        watchlist=WatchlistSummary(
            approaching=[
                ApproachingSetup(
                    title="State BTC Setup",
                    rule_id="STATE-20260330-BTC-01",
                    fields={"Asset": "BTC", "Rule ID": "STATE-20260330-BTC-01"},
                    summary="State summary",
                )
            ],
            alerts=[
                AlertLevel(
                    price="$175",
                    asset="SOL",
                    direction="↑ Break",
                    trigger="Breakout",
                    priority="HIGH",
                )
            ],
        ),
        metadata=StateBundleMetadata(
            source_mode="canonical_state",
            sources={"BTC": "state_json", "SOL": "state_json"},
        ),
    )
    (tmp_path / "state.json").write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for path in (
        tmp_path / "rules.json",
        tmp_path / "positions.json",
        tmp_path / "watchlist.json",
        tmp_path / "prices.json",
    ):
        path.write_text("{}", encoding="utf-8")

    rules_document = repository.get_rules()
    positions_document = repository.get_positions()
    watchlist_document = repository.get_watchlist()
    prices_document = repository.get_prices()
    state_document = repository.get_state()

    assert [rule.rule_id for rule in rules_document.rules] == ["STATE-20260330-BTC-01"]
    assert [position.rule_id for position in positions_document.positions] == [
        "STATE-20260330-BTC-01"
    ]
    assert [setup.rule_id for setup in watchlist_document.watchlist.approaching] == [
        "STATE-20260330-BTC-01"
    ]
    assert prices_document.prices == {"BTC": 71000.0, "SOL": 180.0}
    assert prices_document.sources == {"BTC": "state_json", "SOL": "state_json"}
    assert state_document.metadata.source_mode == "canonical_state"
