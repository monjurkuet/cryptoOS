# src/market_scraper/api/routes/leaderboard_raw.py

"""Raw leaderboard query API.

Provides a REST endpoint to query the full 39K Hyperliquid leaderboard
snapshot with arbitrary filters (ROI, volume, PnL, account value, etc.)
across all time windows.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/query")
async def query_raw_leaderboard(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort_by: str = Query("accountValue", description="Sort field: accountValue, roi_all_time, roi_month, roi_week, roi_day, volume_month, pnl_all_time"),
    sort_desc: bool = Query(True, description="Sort descending"),
    # Account value filters
    min_acct_val: float | None = Query(None, ge=0, description="Minimum account value (USD)"),
    max_acct_val: float | None = Query(None, ge=0, description="Maximum account value (USD)"),
    # ROI filters
    min_roi_all_time: float | None = Query(None, description="Minimum all-time ROI (ratio, e.g. 1.0 = 100%)"),
    max_roi_all_time: float | None = Query(None, description="Maximum all-time ROI"),
    min_roi_month: float | None = Query(None, description="Minimum 30d ROI"),
    max_roi_month: float | None = Query(None, description="Maximum 30d ROI"),
    min_roi_week: float | None = Query(None, description="Minimum 7d ROI"),
    max_roi_week: float | None = Query(None, description="Maximum 7d ROI"),
    min_roi_day: float | None = Query(None, description="Minimum 24h ROI"),
    max_roi_day: float | None = Query(None, description="Maximum 24h ROI"),
    # Volume filters
    min_volume_month: float | None = Query(None, ge=0, description="Minimum 30d volume (USD)"),
    max_volume_month: float | None = Query(None, ge=0, description="Maximum 30d volume (USD)"),
    # PnL filters
    min_pnl_all_time: float | None = Query(None, description="Minimum all-time PnL (USD)"),
    max_pnl_all_time: float | None = Query(None, description="Maximum all-time PnL (USD)"),
    # Boolean filters
    has_positive: str | None = Query(None, description="Comma-separated timeframes requiring positive ROI (e.g. 'allTime,month')"),
    addresses: str | None = Query(None, description="Comma-separated ETH addresses to filter by"),
    fetch_time: str | None = Query(None, description="ISO timestamp to query a specific snapshot (default: latest)"),
) -> dict[str, Any]:
    """Query the raw Hyperliquid leaderboard snapshot with arbitrary filters.

    Returns traders from the latest cached snapshot (all ~39K traders),
    filtered by the provided criteria. Supports pagination and sorting.

    **Examples:**
    - `/api/v1/leaderboard/query?min_acct_val=100000&sort_by=roi_all_time&limit=20`
    - `/api/v1/leaderboard/query?min_roi_all_time=1.0&has_positive=allTime,month`
    - `/api/v1/leaderboard/query?min_volume_month=100000000&sort_by=volume_month`
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    # Parse has_positive from comma-separated string
    positive_list: list[str] | None = None
    if has_positive:
        positive_list = [tf.strip() for tf in has_positive.split(",") if tf.strip()]

    # Parse addresses from comma-separated string
    address_list: list[str] | None = None
    if addresses:
        addr_raw = [a.strip().lower() for a in addresses.split(",") if a.strip()]
        # Validate addresses
        import re

        eth_pattern = re.compile(r"^0x[a-fA-F0-9]{40}$")
        for addr in addr_raw:
            if not eth_pattern.match(addr):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid ETH address: {addr}",
                )
        address_list = addr_raw

    # Parse fetch_time if provided
    parsed_fetch_time: datetime | None = None
    if fetch_time:
        try:
            parsed_fetch_time = datetime.fromisoformat(fetch_time)
            if parsed_fetch_time.tzinfo is None:
                parsed_fetch_time = parsed_fetch_time.replace(tzinfo=UTC)
        except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid fetch_time format: {fetch_time}. Use ISO format (e.g. '2026-06-23T12:00:00Z')",
                ) from None

    result = await repository.get_raw_leaderboard(
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_desc=sort_desc,
        min_acct_val=min_acct_val,
        max_acct_val=max_acct_val,
        min_roi_all_time=min_roi_all_time,
        max_roi_all_time=max_roi_all_time,
        min_roi_month=min_roi_month,
        max_roi_month=max_roi_month,
        min_roi_week=min_roi_week,
        max_roi_week=max_roi_week,
        min_roi_day=min_roi_day,
        max_roi_day=max_roi_day,
        min_volume_month=min_volume_month,
        max_volume_month=max_volume_month,
        min_pnl_all_time=min_pnl_all_time,
        max_pnl_all_time=max_pnl_all_time,
        has_positive=positive_list,
        address_filter=address_list,
        fetch_time=parsed_fetch_time,
    )

    return result


@router.get("/tiers")
async def get_tier_distribution(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get the distribution of tracked traders across cadence tiers.

    and the current tier configuration from market_config.
    """
    repository = lifecycle.repository
    config = lifecycle.market_config

    if not config.filters.tiered_enabled:
        return {
            "tiered_enabled": False,
            "cadence_enabled": config.tracking_cadence.enabled,
            "message": "Tiered filtering is disabled. Enable filters.tiered_enabled in market_config.yaml.",
        }

    # Count traders by cadence tier
    try:
        tier_breakdown = await repository.get_tier_breakdown()

        total_active = sum(t.get("count", 0) for t in tier_breakdown)

        return {
            "tiered_enabled": True,
            "cadence_enabled": config.tracking_cadence.enabled,
            "total_active_tracked": total_active,
            "tier_breakdown": [
                {
                    "tier": t.get("_id", "unknown"),
                    "count": t.get("count", 0),
                    "avg_acct_val": round(float(t.get("avg_acct_val", 0)), 2),
                    "avg_score": round(float(t.get("avg_score", 0)), 2),
                }
                for t in sorted(tier_breakdown, key=lambda x: -x.get("count", 0))
            ],
            "multi_tier_config": [
                {
                    "name": t.name,
                    "max_slots": t.max_slots,
                    "min_account_value": t.min_account_value,
                    "min_score": t.min_score,
                    "min_roi_all_time": t.min_roi_all_time,
                    "min_roi_month": t.min_roi_month,
                }
                for t in config.filters.tiers
            ],
            "cadence_config": {
                k: {
                    "max_traders": v.max_traders,
                    "check_interval_seconds": v.check_interval_seconds,
                    "min_acct_val": v.min_acct_val,
                    "min_month_roi": v.min_month_roi,
                    "min_score": v.min_score,
                }
                for k, v in config.tracking_cadence.tiers.items()
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tier distribution: {e}") from None


@router.post("/run-promotions")
async def run_promotion_evaluation(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Manually trigger a promotion/demotion evaluation cycle."""
    collector = lifecycle.leaderboard_collector
    if collector is None:
        raise HTTPException(
            status_code=503,
            detail="Leaderboard collector not available (service may be initializing)",
        )

    result = await collector.evaluate_promotions()
    return result
