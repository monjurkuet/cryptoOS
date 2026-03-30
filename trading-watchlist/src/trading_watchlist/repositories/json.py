"""JSON-backed repository."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.repositories.models import (
    ManifestDocument,
    PositionsDocument,
    PricesDocument,
    RulesDocument,
    StateDocument,
    WatchlistDocument,
)


class JsonRepository:
    """Repository backed by structured JSON files."""

    def __init__(
        self,
        rules_path: Path,
        positions_path: Path,
        watchlist_path: Path,
        prices_path: Path,
        state_path: Path,
        manifest_path: Path,
    ) -> None:
        self.rules_path = rules_path
        self.positions_path = positions_path
        self.watchlist_path = watchlist_path
        self.prices_path = prices_path
        self.state_path = state_path
        self.manifest_path = manifest_path

    def get_rules(self) -> RulesDocument:
        if self.state_path.exists():
            state = self._get_state_document()
            return RulesDocument(prices=state.prices, rules=state.rules)

        return RulesDocument.model_validate(self._read_json(self.rules_path))

    def get_positions(self) -> PositionsDocument:
        if self.state_path.exists():
            state = self._get_state_document()
            return PositionsDocument(prices=state.prices, positions=state.positions)

        return PositionsDocument.model_validate(self._read_json(self.positions_path))

    def get_watchlist(self) -> WatchlistDocument:
        if self.state_path.exists():
            state = self._get_state_document()
            return WatchlistDocument(prices=state.prices, watchlist=state.watchlist)

        return WatchlistDocument.model_validate(self._read_json(self.watchlist_path))

    def get_prices(self) -> PriceResponse:
        if self.state_path.exists():
            state = self._get_state_document()
            return PricesDocument(prices=state.prices, sources=state.metadata.sources)

        if self.prices_path.exists():
            return PricesDocument.model_validate(self._read_json(self.prices_path))

        prices: dict[str, float] = {}
        sources: dict[str, str] = {}
        for source_name, document in (
            ("rules_json", self.get_rules()),
            ("positions_json", self.get_positions()),
            ("watchlist_json", self.get_watchlist()),
        ):
            for asset, value in document.prices.items():
                prices[asset] = value
                sources[asset] = source_name
        return PriceResponse(prices=prices, sources=sources)

    def get_state(self) -> StateBundle:
        if self.state_path.exists():
            return self._get_state_document()

        rules_document = self.get_rules()
        positions_document = self.get_positions()
        watchlist_document = self.get_watchlist()
        prices_document = self.get_prices()
        generated_at = None
        if self.manifest_path.exists():
            generated_at = ManifestDocument.model_validate(
                self._read_json(self.manifest_path)
            ).generated_at
        return StateBundle(
            generated_at=generated_at or self._latest_generated_at(),
            prices=prices_document.prices,
            rules=rules_document.rules,
            positions=positions_document.positions,
            watchlist=watchlist_document.watchlist,
            metadata=StateBundleMetadata(
                source_mode="structured_json",
                sources=prices_document.sources,
            ),
        )

    def _read_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _get_state_document(self) -> StateDocument:
        return StateDocument.model_validate(self._read_json(self.state_path))

    def _latest_generated_at(self) -> datetime:
        latest_mtime = max(
            path.stat().st_mtime
            for path in (self.rules_path, self.positions_path, self.watchlist_path)
        )
        return datetime.fromtimestamp(latest_mtime, tz=timezone.utc)
