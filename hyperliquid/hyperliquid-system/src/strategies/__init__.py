"""
Strategies Package.

This module provides trading strategy components.
"""

from src.strategies.position_detection import (
    calculate_btc_exposure,
    detect_position_changes,
    get_position_for_coin,
)
from src.strategies.signal_generation import (
    generate_aggregated_signal,
    generate_individual_signal,
)
from src.strategies.trader_scoring import (
    calculate_trader_score,
    filter_btc_active_traders,
    select_top_traders,
    update_trader_scores,
)

__all__ = [
    # Trader Scoring
    "calculate_trader_score",
    "filter_btc_active_traders",
    "select_top_traders",
    "update_trader_scores",
    # Position Detection
    "detect_position_changes",
    "calculate_btc_exposure",
    "get_position_for_coin",
    # Signal Generation
    "generate_individual_signal",
    "generate_aggregated_signal",
]
