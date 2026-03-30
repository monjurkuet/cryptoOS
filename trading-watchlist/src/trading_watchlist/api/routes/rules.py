"""Rule routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from trading_watchlist.api.dependencies import get_watchlist_service
from trading_watchlist.config import get_settings
from trading_watchlist.exporter import persist_state_bundle
from trading_watchlist.models.common import EvaluateRequest, EvaluateResponse, PriceResponse
from trading_watchlist.models.rules import Rule
from trading_watchlist.models.state import StateBundle, StateWriteResponse
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import AlertLevel, ApproachingSetup, WatchlistSummary
from trading_watchlist.services.watchlist import TradingWatchlistService

router = APIRouter()


@router.get("/rules", response_model=list[Rule])
async def list_rules(
    asset: str | None = Query(default=None),
    status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> list[Rule]:
    """Return parsed rules."""

    return service.filter_rules(asset=asset, status=status, direction=direction)


@router.get("/rules/{rule_id}", response_model=Rule)
async def get_rule(
    rule_id: str, service: TradingWatchlistService = Depends(get_watchlist_service)
) -> Rule:
    """Return a single rule."""

    rule = service.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule


@router.get("/positions", response_model=list[Position])
async def list_positions(
    asset: str | None = Query(default=None),
    section: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> list[Position]:
    """Return open and pending positions."""

    return service.filter_positions(asset=asset, section=section, direction=direction)


@router.get("/watchlist", response_model=WatchlistSummary)
async def get_watchlist(
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> WatchlistSummary:
    """Return watchlist summary."""

    _, watchlist = service.get_watchlist()
    return watchlist


@router.get("/approaching", response_model=list[ApproachingSetup])
async def get_approaching(
    asset: str | None = Query(default=None),
    rule_id: str | None = Query(default=None),
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> list[ApproachingSetup]:
    """Return approaching setups."""

    return service.filter_approaching(asset=asset, rule_id=rule_id)


@router.get("/alerts", response_model=list[AlertLevel])
async def get_alerts(
    asset: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> list[AlertLevel]:
    """Return alert levels."""

    return service.filter_alerts(asset=asset, priority=priority)


@router.get("/prices", response_model=PriceResponse)
async def get_prices(
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> PriceResponse:
    """Return normalized prices used by the service."""

    return await service.get_prices()


@router.get("/state", response_model=StateBundle)
async def get_state(
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> StateBundle:
    """Return the canonical structured state bundle."""

    return service.get_state()


@router.put("/state", response_model=StateWriteResponse)
async def write_state(state: StateBundle) -> StateWriteResponse:
    """Persist canonical structured state and regenerate derived artifacts."""

    settings = get_settings()
    return persist_state_bundle(state, settings.json_data_dir, settings.trading_data_dir)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_rules(
    request: EvaluateRequest,
    service: TradingWatchlistService = Depends(get_watchlist_service),
) -> EvaluateResponse:
    """Evaluate parsed rules against current or supplied prices."""

    return await service.evaluate(request)
