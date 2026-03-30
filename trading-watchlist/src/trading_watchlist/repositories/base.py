"""Repository contracts."""

from typing import Protocol

from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.state import StateBundle
from trading_watchlist.repositories.models import (
    PositionsDocument,
    RulesDocument,
    WatchlistDocument,
)


class TradingWatchlistRepository(Protocol):
    """Stable storage contract for the service layer."""

    def get_rules(self) -> RulesDocument: ...

    def get_positions(self) -> PositionsDocument: ...

    def get_watchlist(self) -> WatchlistDocument: ...

    def get_prices(self) -> PriceResponse: ...

    def get_state(self) -> StateBundle: ...
