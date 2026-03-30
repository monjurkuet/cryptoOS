import json
from datetime import datetime, timezone
from pathlib import Path

from trading_watchlist.models.rules import Rule, RuleTarget
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.repositories.models import (
    PositionsDocument,
    PricesDocument,
    RulesDocument,
    WatchlistDocument,
)
from trading_watchlist.writer import (
    CanonicalStateArtifacts,
    CanonicalStateWriter,
    GeneratedMarkdownWriter,
)


def build_artifacts() -> CanonicalStateArtifacts:
    generated_at = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
    rule = Rule(
        rule_id="TEST-20260330-BTC-01",
        asset="BTC",
        timeframe="DAILY",
        direction="SHORT",
        condition="IF BTC loses support THEN lower",
        entry="Below 66,000",
        targets=[
            RuleTarget(label="TP1", value_text="$63,000", min_price=63000.0, max_price=63000.0)
        ],
        invalidation="Above 68,000",
        confidence="HIGH",
        status="ACTIVE",
    )
    position = Position(
        title="#1 - BTC Short",
        rule_id=rule.rule_id,
        section="open",
        direction="SHORT",
        asset="BTC",
    )
    watchlist = WatchlistSummary(
        approaching=[
            ApproachingSetup(
                title="BTC Setup",
                rule_id=rule.rule_id,
                fields={"Asset": "BTC", "Rule ID": rule.rule_id},
                summary="BTC is near trigger.",
            )
        ],
        alerts=[
            AlertLevel(
                price="$65,000",
                asset="BTC",
                direction="↓ Break",
                trigger="Support loss",
                priority="CRITICAL",
            )
        ],
    )
    state = StateBundle(
        generated_at=generated_at,
        prices={"BTC": 66596.0},
        rules=[rule],
        positions=[position],
        watchlist=watchlist,
        metadata=StateBundleMetadata(
            source_mode="markdown_export",
            sources={"BTC": "watchlist_markdown"},
        ),
    )
    return CanonicalStateArtifacts(
        state=state,
        rules=RulesDocument(prices={"BTC": 66596.0}, rules=[rule]),
        positions=PositionsDocument(prices={"BTC": 66596.0}, positions=[position]),
        watchlist=WatchlistDocument(prices={"BTC": 66596.0}, watchlist=watchlist),
        prices=PricesDocument(prices={"BTC": 66596.0}, sources={"BTC": "watchlist_markdown"}),
    )


def test_canonical_state_writer_outputs_expected_files(tmp_path: Path) -> None:
    artifacts = build_artifacts()

    written_paths = CanonicalStateWriter().write(artifacts, tmp_path)

    assert [path.name for path in written_paths] == [
        "rules.json",
        "positions.json",
        "watchlist.json",
        "prices.json",
        "state.json",
        "manifest.json",
    ]
    state_payload = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert state_payload["rules"][0]["rule_id"] == "TEST-20260330-BTC-01"
    assert state_payload["metadata"]["sources"] == {"BTC": "watchlist_markdown"}
    assert manifest_payload["files"]["watchlist"]["filename"] == "watchlist.json"
    assert manifest_payload["generated_at"] == "2026-03-30T12:00:00Z"


def test_generated_markdown_writer_outputs_scaffolds(tmp_path: Path) -> None:
    artifacts = build_artifacts()

    written_paths = GeneratedMarkdownWriter().write(artifacts.state, tmp_path)

    assert [path.name for path in written_paths] == [
        "analysis-rules.generated.md",
        "analysis-trades.generated.md",
        "analysis-watchlist.generated.md",
        "analysis-brief.generated.md",
    ]
    trades = (tmp_path / "analysis-trades.generated.md").read_text(encoding="utf-8")
    brief = (tmp_path / "analysis-brief.generated.md").read_text(encoding="utf-8")
    watchlist = (tmp_path / "analysis-watchlist.generated.md").read_text(encoding="utf-8")

    assert "- Open positions: 1" in trades
    assert "- Section: `open`" in trades
    assert "Generated scaffold from canonical structured state" in brief
    assert "This scaffold is generated from `state.json`" in brief
    assert "## Alerts" in watchlist
    assert "BTC Setup" in watchlist
