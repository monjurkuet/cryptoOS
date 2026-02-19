# src/market_scraper/processors/__init__.py

"""Processing pipeline for the Market Scraper Framework.

This module provides processors that transform, validate, enrich, and aggregate
events as they flow through the system.

Available Processors:
    - Processor: Abstract base class for all processors
    - MarketDataProcessor: Normalizes and validates market data events
    - CandleProcessor: Aggregates trades into OHLCV candles
    - MetricsProcessor: Collects and emits system metrics
    - PositionInferenceProcessor: Infers trader positions from leaderboard
    - TraderScoringProcessor: Scores traders from leaderboard data
    - SignalGenerationProcessor: Generates trading signals
"""

from market_scraper.processors.base import Processor
from market_scraper.processors.candle_processor import CandleProcessor
from market_scraper.processors.market_processor import MarketDataProcessor
from market_scraper.processors.metrics_processor import MetricsProcessor
from market_scraper.processors.position_inference import PositionInferenceProcessor
from market_scraper.processors.position_detection import PositionDetectionProcessor
from market_scraper.processors.trader_scoring import TraderScoringProcessor
from market_scraper.processors.signal_generation import SignalGenerationProcessor

__all__ = [
    "Processor",
    "MarketDataProcessor",
    "CandleProcessor",
    "MetricsProcessor",
    "PositionInferenceProcessor",
    "PositionDetectionProcessor",
    "TraderScoringProcessor",
    "SignalGenerationProcessor",
]
