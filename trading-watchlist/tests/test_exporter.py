import json
from pathlib import Path

from trading_watchlist.exporter import (
    export_markdown_to_json,
    main,
    persist_state_bundle,
    refresh_from_state,
    refresh_main,
    write_state_main,
)
from trading_watchlist.models.rules import Rule, RuleTarget
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.repositories.markdown import MarkdownRepository
from tests.helpers import write_markdown_dataset


def test_exporter_generates_json_from_markdown(tmp_path: Path) -> None:
    write_markdown_dataset(tmp_path)

    output_dir = tmp_path / "data"
    repository = MarkdownRepository(
        rules_path=tmp_path / "analysis-rules.md",
        trades_path=tmp_path / "analysis-trades.md",
        watchlist_path=tmp_path / "analysis-watchlist.md",
    )

    written_paths = export_markdown_to_json(repository, output_dir)

    assert [path.name for path in written_paths] == [
        "rules.json",
        "positions.json",
        "watchlist.json",
        "prices.json",
        "state.json",
        "manifest.json",
        "analysis-rules.generated.md",
        "analysis-trades.generated.md",
        "analysis-watchlist.generated.md",
        "analysis-brief.generated.md",
    ]
    rules_payload = json.loads((output_dir / "rules.json").read_text(encoding="utf-8"))
    prices_payload = json.loads((output_dir / "prices.json").read_text(encoding="utf-8"))
    state_payload = json.loads((output_dir / "state.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert rules_payload["rules"][0]["rule_id"] == "EXPORT-20260330-BTC-01"
    assert rules_payload["prices"]["BTC"] == 66596.0
    assert prices_payload["sources"]["BTC"] == "watchlist_markdown"
    assert state_payload["schema_version"] == "v1"
    assert state_payload["rules"][0]["rule_id"] == "EXPORT-20260330-BTC-01"
    assert state_payload["metadata"]["source_mode"] == "markdown_export"
    assert manifest_payload["schema_version"] == "v1"
    assert manifest_payload["source_mode"] == "markdown_export"
    assert manifest_payload["files"]["state"]["filename"] == "state.json"
    assert "Generated scaffold from canonical structured state" in (
        output_dir.parent / "analysis-brief.generated.md"
    ).read_text(encoding="utf-8")


def test_seed_cli_uses_writer_path(tmp_path: Path, monkeypatch) -> None:
    write_markdown_dataset(tmp_path)

    structured_data_dir = tmp_path / "data"
    generated_markdown_dir = tmp_path / "generated"
    calls: list[tuple[str, Path]] = []

    def fake_state_write(self, artifacts, output_dir):
        calls.append(("state", output_dir))
        assert artifacts.state.metadata.source_mode == "markdown_export"
        return []

    def fake_markdown_write(self, state, output_dir):
        calls.append(("markdown", output_dir))
        assert state.rules[0].rule_id == "EXPORT-20260330-BTC-01"
        return []

    monkeypatch.setattr("trading_watchlist.exporter.CanonicalStateWriter.write", fake_state_write)
    monkeypatch.setattr(
        "trading_watchlist.exporter.GeneratedMarkdownWriter.write", fake_markdown_write
    )

    exit_code = main(
        [
            "--trading-data-dir",
            str(tmp_path),
            "--structured-data-dir",
            str(structured_data_dir),
            "--generated-markdown-dir",
            str(generated_markdown_dir),
        ]
    )

    assert exit_code == 0
    assert calls == [
        ("state", structured_data_dir),
        ("markdown", generated_markdown_dir),
    ]


def test_refresh_from_state_rewrites_split_files_and_generated_markdown(tmp_path: Path) -> None:
    structured_data_dir = tmp_path / "data"
    generated_markdown_dir = tmp_path / "generated"
    structured_data_dir.mkdir()

    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 71234.0, "ETH": 2450.0},
        rules=[
            Rule(
                rule_id="STATE-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC reclaims resistance THEN higher",
                entry="Above 71,000",
                targets=[
                    RuleTarget(
                        label="TP1",
                        value_text="$73,000",
                        min_price=73000.0,
                        max_price=73000.0,
                    )
                ],
                invalidation="Below 69,500",
                confidence="HIGH",
                status="ACTIVE",
            )
        ],
        positions=[
            Position(
                title="#1 - Canonical Position",
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
                    title="Canonical BTC Setup",
                    rule_id="STATE-20260330-BTC-01",
                    fields={"Asset": "BTC", "Rule ID": "STATE-20260330-BTC-01"},
                    summary="Setup summary",
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
        ),
        metadata=StateBundleMetadata(
            source_mode="canonical_state",
            sources={"BTC": "state_json", "ETH": "state_json"},
        ),
    )
    (structured_data_dir / "state.json").write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (structured_data_dir / "rules.json").write_text(
        json.dumps({"prices": {"BTC": 1.0}, "rules": []}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    written_paths = refresh_from_state(structured_data_dir, generated_markdown_dir)

    assert [path.name for path in written_paths] == [
        "rules.json",
        "positions.json",
        "watchlist.json",
        "prices.json",
        "state.json",
        "manifest.json",
        "analysis-rules.generated.md",
        "analysis-trades.generated.md",
        "analysis-watchlist.generated.md",
        "analysis-brief.generated.md",
    ]
    rules_payload = json.loads((structured_data_dir / "rules.json").read_text(encoding="utf-8"))
    prices_payload = json.loads((structured_data_dir / "prices.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads(
        (structured_data_dir / "manifest.json").read_text(encoding="utf-8")
    )

    assert rules_payload["rules"][0]["rule_id"] == "STATE-20260330-BTC-01"
    assert rules_payload["prices"] == {"BTC": 71234.0, "ETH": 2450.0}
    assert prices_payload == {
        "prices": {"BTC": 71234.0, "ETH": 2450.0},
        "sources": {"BTC": "state_json", "ETH": "state_json"},
    }
    assert manifest_payload["files"]["state"]["filename"] == "state.json"
    assert "Canonical BTC Setup" in (
        generated_markdown_dir / "analysis-watchlist.generated.md"
    ).read_text(encoding="utf-8")


def test_refresh_cli_uses_refresh_path(tmp_path: Path, monkeypatch) -> None:
    structured_data_dir = tmp_path / "data"
    generated_markdown_dir = tmp_path / "generated"
    calls: list[tuple[Path, Path]] = []

    def fake_refresh(structured_data_dir_arg: Path, generated_markdown_dir_arg: Path) -> list[Path]:
        calls.append((structured_data_dir_arg, generated_markdown_dir_arg))
        return []

    monkeypatch.setattr("trading_watchlist.exporter.refresh_from_state", fake_refresh)

    exit_code = refresh_main(
        [
            "--structured-data-dir",
            str(structured_data_dir),
            "--generated-markdown-dir",
            str(generated_markdown_dir),
        ]
    )

    assert exit_code == 0
    assert calls == [(structured_data_dir, generated_markdown_dir)]


def test_persist_state_bundle_writes_all_artifacts(tmp_path: Path) -> None:
    structured_data_dir = tmp_path / "data"
    generated_markdown_dir = tmp_path / "generated"
    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 71500.0, "ETH": 2425.0},
        rules=[
            Rule(
                rule_id="PERSIST-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC confirms THEN higher",
                entry="Above 71,000",
                targets=[
                    RuleTarget(
                        label="TP1",
                        value_text="$73,000",
                        min_price=73000.0,
                        max_price=73000.0,
                    )
                ],
                invalidation="Below 70,000",
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

    result = persist_state_bundle(state, structured_data_dir, generated_markdown_dir)

    assert result.schema_version == "v1"
    assert result.source_mode == "canonical_state"
    assert result.written_files == [
        str(structured_data_dir / "rules.json"),
        str(structured_data_dir / "positions.json"),
        str(structured_data_dir / "watchlist.json"),
        str(structured_data_dir / "prices.json"),
        str(structured_data_dir / "state.json"),
        str(structured_data_dir / "manifest.json"),
        str(generated_markdown_dir / "analysis-rules.generated.md"),
        str(generated_markdown_dir / "analysis-trades.generated.md"),
        str(generated_markdown_dir / "analysis-watchlist.generated.md"),
        str(generated_markdown_dir / "analysis-brief.generated.md"),
    ]
    assert (
        json.loads((structured_data_dir / "state.json").read_text(encoding="utf-8"))["rules"][0][
            "rule_id"
        ]
        == "PERSIST-20260330-BTC-01"
    )


def test_write_state_cli_persists_from_input_file(tmp_path: Path) -> None:
    structured_data_dir = tmp_path / "data"
    generated_markdown_dir = tmp_path / "generated"
    input_path = tmp_path / "input-state.json"
    state = StateBundle(
        generated_at="2026-03-30T12:00:00Z",
        prices={"BTC": 71800.0, "ETH": 2475.0},
        rules=[
            Rule(
                rule_id="CLI-20260330-BTC-01",
                asset="BTC",
                timeframe="DAILY",
                direction="LONG",
                condition="IF BTC stays bid THEN higher",
                entry="Above 71,200",
                targets=[
                    RuleTarget(
                        label="TP1",
                        value_text="$74,500",
                        min_price=74500.0,
                        max_price=74500.0,
                    )
                ],
                invalidation="Below 70,200",
                confidence="HIGH",
                status="ACTIVE",
            )
        ],
        positions=[],
        watchlist=WatchlistSummary(
            approaching=[
                ApproachingSetup(
                    title="CLI Setup",
                    rule_id="CLI-20260330-BTC-01",
                    fields={"Asset": "BTC", "Rule ID": "CLI-20260330-BTC-01"},
                    summary="CLI-written setup",
                )
            ]
        ),
        metadata=StateBundleMetadata(
            source_mode="canonical_state",
            sources={"BTC": "state_json", "ETH": "state_json"},
        ),
    )
    input_path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    exit_code = write_state_main(
        [
            "--input",
            str(input_path),
            "--structured-data-dir",
            str(structured_data_dir),
            "--generated-markdown-dir",
            str(generated_markdown_dir),
        ]
    )

    assert exit_code == 0
    assert (
        json.loads((structured_data_dir / "manifest.json").read_text(encoding="utf-8"))["files"][
            "state"
        ]["filename"]
        == "state.json"
    )
    assert json.loads((structured_data_dir / "prices.json").read_text(encoding="utf-8")) == {
        "prices": {"BTC": 71800.0, "ETH": 2475.0},
        "sources": {"BTC": "state_json", "ETH": "state_json"},
    }
    assert "CLI Setup" in (generated_markdown_dir / "analysis-watchlist.generated.md").read_text(
        encoding="utf-8"
    )
