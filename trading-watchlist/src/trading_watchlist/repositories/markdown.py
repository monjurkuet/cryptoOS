"""Markdown-backed repository."""

from datetime import datetime, timezone

from pathlib import Path

from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.state import StateBundle, StateBundleMetadata
from trading_watchlist.parser.rules import parse_rules
from trading_watchlist.parser.trades import parse_positions
from trading_watchlist.parser.watchlist import parse_watchlist
from trading_watchlist.repositories.models import (
    PositionsDocument,
    RulesDocument,
    WatchlistDocument,
)


class MarkdownRepository:
    """Repository backed by the current markdown files."""

    def __init__(self, rules_path: Path, trades_path: Path, watchlist_path: Path) -> None:
        self.rules_path = rules_path
        self.trades_path = trades_path
        self.watchlist_path = watchlist_path

    def get_rules(self) -> RulesDocument:
        prices, rules = parse_rules(self.rules_path.read_text(encoding="utf-8"))
        return RulesDocument(prices=prices, rules=rules)

    def get_positions(self) -> PositionsDocument:
        prices, positions = parse_positions(self.trades_path.read_text(encoding="utf-8"))
        return PositionsDocument(prices=prices, positions=positions)

    def get_watchlist(self) -> WatchlistDocument:
        prices, watchlist = parse_watchlist(self.watchlist_path.read_text(encoding="utf-8"))
        return WatchlistDocument(prices=prices, watchlist=watchlist)

    def get_prices(self) -> PriceResponse:
        prices: dict[str, float] = {}
        sources: dict[str, str] = {}
        for source_name, document in (
            ("rules_markdown", self.get_rules()),
            ("trades_markdown", self.get_positions()),
            ("watchlist_markdown", self.get_watchlist()),
        ):
            for asset, value in document.prices.items():
                prices[asset] = value
                sources[asset] = source_name
        return PriceResponse(prices=prices, sources=sources)

    def get_state(self) -> StateBundle:
        rules_document = self.get_rules()
        positions_document = self.get_positions()
        watchlist_document = self.get_watchlist()
        prices_document = self.get_prices()
        return StateBundle(
            generated_at=datetime.now(timezone.utc),
            prices=prices_document.prices,
            rules=rules_document.rules,
            positions=positions_document.positions,
            watchlist=watchlist_document.watchlist,
            metadata=StateBundleMetadata(source_mode="markdown", sources=prices_document.sources),
        )
