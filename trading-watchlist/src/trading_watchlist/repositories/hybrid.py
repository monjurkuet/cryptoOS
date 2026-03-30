"""Hybrid repository with JSON-first fallback behavior."""

from datetime import datetime, timezone

from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.repositories.base import TradingWatchlistRepository
from trading_watchlist.repositories.json import JsonRepository
from trading_watchlist.repositories.markdown import MarkdownRepository
from trading_watchlist.repositories.models import (
    PositionsDocument,
    RulesDocument,
    WatchlistDocument,
)


class HybridRepository:
    """Prefer structured JSON when present and fall back to markdown."""

    def __init__(
        self,
        markdown_repository: MarkdownRepository,
        json_repository: JsonRepository,
    ) -> None:
        self._markdown_repository = markdown_repository
        self._json_repository = json_repository

    def get_rules(self) -> RulesDocument:
        repository = self._json_repository if self._has_json_rules() else self._markdown_repository
        return repository.get_rules()

    def get_positions(self) -> PositionsDocument:
        repository = (
            self._json_repository if self._has_json_positions() else self._markdown_repository
        )
        return repository.get_positions()

    def get_watchlist(self) -> WatchlistDocument:
        repository = (
            self._json_repository if self._has_json_watchlist() else self._markdown_repository
        )
        return repository.get_watchlist()

    def get_prices(self) -> PriceResponse:
        if self._has_json_prices():
            return self._json_repository.get_prices()

        prices: dict[str, float] = {}
        sources: dict[str, str] = {}
        for source_name, document in (
            (
                "rules_json" if self._json_repository.rules_path.exists() else "rules_markdown",
                self.get_rules(),
            ),
            (
                "positions_json"
                if self._json_repository.positions_path.exists()
                else "trades_markdown",
                self.get_positions(),
            ),
            (
                "watchlist_json"
                if self._json_repository.watchlist_path.exists()
                else "watchlist_markdown",
                self.get_watchlist(),
            ),
        ):
            for asset, value in document.prices.items():
                prices[asset] = value
                sources[asset] = source_name
        return PriceResponse(prices=prices, sources=sources)

    def get_state(self) -> StateBundle:
        if self._json_repository.state_path.exists():
            return self._json_repository.get_state()

        rules_document = self.get_rules()
        positions_document = self.get_positions()
        watchlist_document = self.get_watchlist()
        prices_document = self.get_prices()

        source_mode = "markdown"
        has_json = any(
            path.exists()
            for path in (
                self._json_repository.rules_path,
                self._json_repository.positions_path,
                self._json_repository.watchlist_path,
                self._json_repository.prices_path,
            )
        )
        if has_json:
            source_mode = "structured_json"
            if any(source.endswith("markdown") for source in prices_document.sources.values()):
                source_mode = "hybrid"

        return StateBundle(
            generated_at=datetime.now(timezone.utc),
            prices=prices_document.prices,
            rules=rules_document.rules,
            positions=positions_document.positions,
            watchlist=watchlist_document.watchlist,
            metadata=StateBundleMetadata(source_mode=source_mode, sources=prices_document.sources),
        )

    def _has_json_rules(self) -> bool:
        return (
            self._json_repository.state_path.exists() or self._json_repository.rules_path.exists()
        )

    def _has_json_positions(self) -> bool:
        return (
            self._json_repository.state_path.exists()
            or self._json_repository.positions_path.exists()
        )

    def _has_json_watchlist(self) -> bool:
        return (
            self._json_repository.state_path.exists()
            or self._json_repository.watchlist_path.exists()
        )

    def _has_json_prices(self) -> bool:
        return (
            self._json_repository.state_path.exists() or self._json_repository.prices_path.exists()
        )


def ensure_repository_contract(
    repository: TradingWatchlistRepository,
) -> TradingWatchlistRepository:
    """Keep dependency wiring typed against the protocol."""

    return repository
