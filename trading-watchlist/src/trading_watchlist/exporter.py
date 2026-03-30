"""Structured artifact export and refresh utilities."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from trading_watchlist.config import Settings
from trading_watchlist.models.state import StateBundle, StateBundleMetadata, StateWriteResponse
from trading_watchlist.repositories.json import JsonRepository
from trading_watchlist.repositories.markdown import MarkdownRepository
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


def build_export_artifacts(markdown_repository: MarkdownRepository) -> CanonicalStateArtifacts:
    """Build canonical export artifacts from markdown-backed documents."""

    generated_at = datetime.now(timezone.utc)
    rules_document = markdown_repository.get_rules()
    positions_document = markdown_repository.get_positions()
    watchlist_document = markdown_repository.get_watchlist()
    prices_snapshot = markdown_repository.get_prices()
    prices_document = PricesDocument(
        prices=prices_snapshot.prices,
        sources=prices_snapshot.sources,
    )

    return CanonicalStateArtifacts(
        state=StateBundle(
            generated_at=generated_at,
            prices=prices_document.prices,
            rules=rules_document.rules,
            positions=positions_document.positions,
            watchlist=watchlist_document.watchlist,
            metadata=StateBundleMetadata(
                source_mode="markdown_export",
                sources=prices_document.sources,
            ),
        ),
        rules=rules_document,
        positions=positions_document,
        watchlist=watchlist_document,
        prices=prices_document,
    )


def build_state_artifacts(state: StateBundle) -> CanonicalStateArtifacts:
    """Build split structured artifacts from canonical state."""

    prices_document = PricesDocument(prices=state.prices, sources=state.metadata.sources)
    return CanonicalStateArtifacts(
        state=state,
        rules=RulesDocument(prices=state.prices, rules=state.rules),
        positions=PositionsDocument(prices=state.prices, positions=state.positions),
        watchlist=WatchlistDocument(prices=state.prices, watchlist=state.watchlist),
        prices=prices_document,
    )


def persist_state_bundle(
    state: StateBundle,
    structured_data_dir: Path,
    generated_markdown_dir: Path,
) -> StateWriteResponse:
    """Persist canonical state and regenerate all derived artifacts."""

    artifacts = build_state_artifacts(state)
    written_paths = CanonicalStateWriter().write(artifacts, structured_data_dir)
    written_paths.extend(GeneratedMarkdownWriter().write(artifacts.state, generated_markdown_dir))
    return StateWriteResponse(
        schema_version=artifacts.state.schema_version,
        source_mode=artifacts.state.metadata.source_mode,
        written_files=[str(path) for path in written_paths],
    )


def export_markdown_to_json(
    markdown_repository: MarkdownRepository,
    output_dir: Path,
    generated_markdown_dir: Path | None = None,
) -> list[Path]:
    """Export markdown-backed documents into JSON and generated markdown scaffolds."""

    result = persist_state_bundle(
        build_export_artifacts(markdown_repository).state,
        output_dir,
        generated_markdown_dir or output_dir.parent,
    )
    return [Path(path) for path in result.written_files]


def refresh_from_state(
    structured_data_dir: Path,
    generated_markdown_dir: Path,
) -> list[Path]:
    """Rewrite split JSON artifacts and generated markdown from canonical state."""

    repository = JsonRepository(
        rules_path=structured_data_dir / "rules.json",
        positions_path=structured_data_dir / "positions.json",
        watchlist_path=structured_data_dir / "watchlist.json",
        prices_path=structured_data_dir / "prices.json",
        state_path=structured_data_dir / "state.json",
        manifest_path=structured_data_dir / "manifest.json",
    )
    result = persist_state_bundle(
        repository.get_state(), structured_data_dir, generated_markdown_dir
    )
    return [Path(path) for path in result.written_files]


def refresh_main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for refreshing derived artifacts from canonical state."""

    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Refresh split JSON artifacts and generated markdown from state.json."
    )
    parser.add_argument(
        "--structured-data-dir",
        default=str(settings.json_data_dir),
        help="Directory containing canonical state.json and derived JSON artifacts.",
    )
    parser.add_argument(
        "--generated-markdown-dir",
        default=str(settings.trading_data_dir),
        help="Directory where generated markdown scaffold files will be written.",
    )
    args = parser.parse_args(argv)

    written_paths = refresh_from_state(
        Path(args.structured_data_dir),
        Path(args.generated_markdown_dir),
    )
    for path in written_paths:
        print(path)
    return 0


def write_state_main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for persisting canonical state from a JSON file."""

    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Write canonical structured state and regenerate derived artifacts from input JSON."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a JSON file containing a validated StateBundle payload.",
    )
    parser.add_argument(
        "--structured-data-dir",
        default=str(settings.json_data_dir),
        help="Directory where canonical state.json and derived JSON files will be written.",
    )
    parser.add_argument(
        "--generated-markdown-dir",
        default=str(settings.trading_data_dir),
        help="Directory where generated markdown scaffold files will be written.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    state = StateBundle.model_validate_json(input_path.read_text(encoding="utf-8"))
    result = persist_state_bundle(
        state,
        Path(args.structured_data_dir),
        Path(args.generated_markdown_dir),
    )
    for path in result.written_files:
        print(path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for seeding structured JSON from markdown."""

    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Seed canonical structured state and generated markdown from markdown files."
    )
    parser.add_argument(
        "--trading-data-dir",
        default=str(settings.trading_data_dir),
        help="Directory containing analysis markdown files.",
    )
    parser.add_argument(
        "--structured-data-dir",
        default=str(settings.json_data_dir),
        help="Directory where structured JSON files will be written.",
    )
    parser.add_argument(
        "--generated-markdown-dir",
        default=str(settings.trading_data_dir),
        help="Directory where generated markdown scaffold files will be written.",
    )
    args = parser.parse_args(argv)

    trading_data_dir = Path(args.trading_data_dir)
    markdown_repository = MarkdownRepository(
        rules_path=trading_data_dir / "analysis-rules.md",
        trades_path=trading_data_dir / "analysis-trades.md",
        watchlist_path=trading_data_dir / "analysis-watchlist.md",
    )
    written_paths = export_markdown_to_json(
        markdown_repository,
        Path(args.structured_data_dir),
        generated_markdown_dir=Path(args.generated_markdown_dir),
    )
    for path in written_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
