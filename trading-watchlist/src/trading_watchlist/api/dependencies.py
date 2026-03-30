"""API dependencies."""

from trading_watchlist.config import get_settings
from trading_watchlist.repositories.hybrid import HybridRepository, ensure_repository_contract
from trading_watchlist.repositories.json import JsonRepository
from trading_watchlist.repositories.markdown import MarkdownRepository
from trading_watchlist.services.market_data import MarketDataService
from trading_watchlist.services.watchlist import TradingWatchlistService


def get_watchlist_service() -> TradingWatchlistService:
    """Construct the service from settings."""

    settings = get_settings()
    repository = ensure_repository_contract(
        HybridRepository(
            markdown_repository=MarkdownRepository(
                rules_path=settings.rules_path,
                trades_path=settings.trades_path,
                watchlist_path=settings.watchlist_path,
            ),
            json_repository=JsonRepository(
                rules_path=settings.rules_json_path,
                positions_path=settings.positions_json_path,
                watchlist_path=settings.watchlist_json_path,
                prices_path=settings.prices_json_path,
                state_path=settings.state_json_path,
                manifest_path=settings.manifest_json_path,
            ),
        )
    )
    return TradingWatchlistService(
        repository=repository,
        market_data_service=MarketDataService(settings.btc_market_url),
    )
