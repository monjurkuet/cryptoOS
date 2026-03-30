"""Canonical structured state writer."""

from datetime import datetime
import json
from pathlib import Path

from pydantic import BaseModel

from trading_watchlist.models.state import ManifestFileEntry, StateBundle, StateManifest
from trading_watchlist.repositories.models import (
    PositionsDocument,
    PricesDocument,
    RulesDocument,
    WatchlistDocument,
)


class CanonicalStateArtifacts(BaseModel):
    """Structured documents written together as one export."""

    state: StateBundle
    rules: RulesDocument
    positions: PositionsDocument
    watchlist: WatchlistDocument
    prices: PricesDocument


class CanonicalStateWriter:
    """Write the canonical state bundle and split JSON artifacts."""

    file_names = {
        "rules": "rules.json",
        "positions": "positions.json",
        "watchlist": "watchlist.json",
        "prices": "prices.json",
        "state": "state.json",
        "manifest": "manifest.json",
    }

    def write(
        self,
        artifacts: CanonicalStateArtifacts,
        output_dir: Path,
        *,
        generated_at: datetime | None = None,
        source_mode: str | None = None,
    ) -> list[Path]:
        """Write the canonical JSON export set."""

        output_dir.mkdir(parents=True, exist_ok=True)
        generated_at = generated_at or artifacts.state.generated_at
        source_mode = source_mode or artifacts.state.metadata.source_mode
        manifest = self._build_manifest(generated_at=generated_at, source_mode=source_mode)

        payloads = {
            output_dir / self.file_names["rules"]: artifacts.rules.model_dump(mode="json"),
            output_dir / self.file_names["positions"]: artifacts.positions.model_dump(mode="json"),
            output_dir / self.file_names["watchlist"]: artifacts.watchlist.model_dump(mode="json"),
            output_dir / self.file_names["prices"]: artifacts.prices.model_dump(mode="json"),
            output_dir / self.file_names["state"]: artifacts.state.model_dump(mode="json"),
            output_dir / self.file_names["manifest"]: manifest.model_dump(mode="json"),
        }

        written_paths: list[Path] = []
        for path, payload in payloads.items():
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            written_paths.append(path)
        return written_paths

    def _build_manifest(self, *, generated_at: datetime, source_mode: str) -> StateManifest:
        return StateManifest(
            generated_at=generated_at,
            source_mode=source_mode,
            files={
                key: ManifestFileEntry(filename=filename, generated_at=generated_at)
                for key, filename in self.file_names.items()
            },
        )
