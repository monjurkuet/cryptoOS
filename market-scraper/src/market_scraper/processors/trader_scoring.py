# src/market_scraper/processors/trader_scoring.py

"""Trader Scoring Processor.

Scores traders based on multi-factor performance metrics.
Weights: All-time ROI (30%), Month ROI (25%), Week ROI (20%),
Account Value (15%), Volume (10%).
"""

from typing import Any

import structlog

from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor
from market_scraper.utils.hyperliquid import (
    extract_roi,
    extract_volume,
    is_positive_roi,
    parse_window_performances,
)

logger = structlog.get_logger(__name__)


def calculate_trader_score(trader: dict[str, Any]) -> float:
    """Calculate a score for a trader based on performance metrics.

    Scoring weights:
    - All-time ROI: 30%
    - Month ROI: 25%
    - Week ROI: 20%
    - Account value: 15%
    - Volume: 10%
    - Bonus: +5% for consistent positive performance

    Args:
        trader: Trader data dictionary from leaderboard

    Returns:
        Calculated score (0-100+)
    """
    score = 0.0

    # Parse performances using shared utility
    performances = parse_window_performances(trader.get("windowPerformances", {}))

    # All-time ROI (30% weight, max 30 points)
    all_time_roi = extract_roi(performances, "allTime")
    score += min(all_time_roi * 30, 30)

    # Month ROI (25% weight, max 25 points)
    month_roi = extract_roi(performances, "month")
    score += min(month_roi * 50, 25)

    # Week ROI (20% weight, max 20 points, can be negative)
    week_roi = extract_roi(performances, "week")
    score += max(min(week_roi * 100, 20), -10)

    # Account value (15% weight, max 15 points)
    account_value = float(trader.get("accountValue", 0))
    if account_value >= 10_000_000:
        score += 15
    elif account_value >= 5_000_000:
        score += 12
    elif account_value >= 1_000_000:
        score += 8
    elif account_value >= 100_000:
        score += 4

    # Volume (10% weight, max 10 points)
    month_volume = extract_volume(performances, "month")
    if month_volume >= 100_000_000:
        score += 10
    elif month_volume >= 50_000_000:
        score += 7
    elif month_volume >= 10_000_000:
        score += 4
    elif month_volume >= 1_000_000:
        score += 2

    # Bonus: Positive consistency (all timeframes positive)
    if is_positive_roi(performances, "day", "week", "month"):
        score += 5

    return round(score, 2)


def get_trader_tags(trader: dict[str, Any], score: float) -> list[str]:
    """Generate tags for a trader based on their metrics.

    Args:
        trader: Trader data dictionary
        score: Calculated trader score

    Returns:
        List of applicable tags
    """
    tags = []

    account_value = float(trader.get("accountValue", 0))
    performances = parse_window_performances(trader.get("windowPerformances", {}))

    # Score-based tags
    if score >= 80:
        tags.append("top_performer")
    if score >= 90:
        tags.append("elite")

    # Size-based tags
    if account_value >= 10_000_000:
        tags.append("whale")
    elif account_value >= 1_000_000:
        tags.append("large")

    # Consistency tags
    all_time_roi = extract_roi(performances, "allTime")
    month_roi = extract_roi(performances, "month")
    week_roi = extract_roi(performances, "week")

    if all_time_roi > 0 and month_roi > 0 and week_roi > 0:
        tags.append("consistent")

    if all_time_roi > 1.0:  # 100%+ all-time ROI
        tags.append("high_performer")

    return tags


class TraderScoringProcessor(Processor):
    """Processor that scores traders from leaderboard data.

    Emits 'scored_traders' events with scored and ranked traders.
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings | None = None,
        min_score: float = 50.0,
        max_count: int = 500,
    ) -> None:
        """Initialize the processor.

        Args:
            event_bus: Event bus for publishing events
            config: Optional Hyperliquid settings
            min_score: Minimum score threshold
            max_count: Maximum traders to return
        """
        super().__init__(event_bus)
        self._config = config
        self._min_score = min_score
        self._max_count = max_count

        # Stats
        self._processed = 0
        self._scored = 0

    @property
    def name(self) -> str:
        """Processor name."""
        return "trader_scoring"

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process a leaderboard event and score traders.

        Args:
            event: Event containing leaderboard data

        Returns:
            Scored traders event or None
        """
        if event.event_type != "leaderboard":
            return None

        self._processed += 1

        payload = event.payload
        if not isinstance(payload, dict):
            return None

        rows = payload.get("rows", [])
        if not rows:
            rows = payload.get("traders", [])

        if not rows:
            return None

        # Score all traders
        scored_traders = []

        for trader in rows:
            score = calculate_trader_score(trader)

            if score >= self._min_score:
                address = trader.get("ethAddress", "")
                tags = get_trader_tags(trader, score)

                scored_traders.append(
                    {
                        "address": address,
                        "displayName": trader.get("displayName"),
                        "accountValue": float(trader.get("accountValue", 0)),
                        "score": score,
                        "tags": tags,
                        "windowPerformances": trader.get("windowPerformances", []),
                    }
                )

        # Sort by score descending
        scored_traders.sort(key=lambda x: x["score"], reverse=True)

        # Limit to max_count
        selected = scored_traders[: self._max_count]

        self._scored += len(selected)

        if selected:
            return StandardEvent.create(
                event_type="scored_traders",
                source="trader_scoring",
                payload={
                    "symbol": self._config.symbol if self._config else "BTC",
                    "count": len(selected),
                    "traders": selected,
                    "stats": {
                        "total_scored": len(scored_traders),
                        "selected": len(selected),
                        "min_score": self._min_score,
                    },
                },
            )

        return None

    def get_stats(self) -> dict[str, int]:
        """Get processor statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "processed": self._processed,
            "scored_traders": self._scored,
        }
