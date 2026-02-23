# src/market_scraper/processors/__init__.py

"""Processing pipeline for the Market Scraper Framework.

This module provides processors that transform, validate, enrich, and aggregate
events as they flow through the system.

Available Processors:
    - Processor: Abstract base class for all processors
    - PositionInferenceProcessor: Infers trader positions from leaderboard
    - TraderScoringProcessor: Scores traders from leaderboard data
    - SignalGenerationProcessor: Generates trading signals
"""

from market_scraper.processors.base import Processor
from market_scraper.processors.position_inference import PositionInferenceProcessor
from market_scraper.processors.signal_generation import SignalGenerationProcessor
from market_scraper.processors.trader_scoring import TraderScoringProcessor

__all__ = [
    "Processor",
    "PositionInferenceProcessor",
    "TraderScoringProcessor",
    "SignalGenerationProcessor",
]
