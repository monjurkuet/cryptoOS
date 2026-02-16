"""
Configuration module for the Hyperliquid BTC Trading System.

This module provides centralized configuration management using Pydantic Settings.
All configuration values can be overridden via environment variables.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    Environment variables take precedence over .env file values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # MongoDB Configuration
    # =========================================================================
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI",
    )
    mongodb_db_name: str = Field(
        default="hyperliquid_btc",
        description="MongoDB database name",
    )

    # =========================================================================
    # API Endpoints
    # =========================================================================
    hyperliquid_api_url: str = Field(
        default="https://api.hyperliquid.xyz/info",
        description="Hyperliquid API endpoint",
    )
    cloudfront_base_url: str = Field(
        default="https://d2v1fiwobg9w6.cloudfront.net",
        description="CloudFront CDN base URL",
    )
    stats_data_url: str = Field(
        default="https://stats-data.hyperliquid.xyz",
        description="Hyperliquid stats data URL",
    )

    # =========================================================================
    # Collection Intervals (seconds)
    # =========================================================================
    candles_interval: int = Field(default=300, description="Candles collection interval")
    orderbook_interval: int = Field(default=30, description="Orderbook collection interval")
    trades_interval: int = Field(default=60, description="Trades collection interval")
    ticker_interval: int = Field(default=60, description="Ticker update interval")
    funding_interval: int = Field(
        default=28800, description="Funding collection interval (8 hours)"
    )
    trader_positions_interval: int = Field(default=60, description="Trader positions interval")
    trader_orders_interval: int = Field(default=300, description="Trader orders interval")
    signals_interval: int = Field(default=30, description="Signal generation interval")

    # =========================================================================
    # Retention Policy (days)
    # =========================================================================
    candles_1m_retention: int = Field(default=30, description="1m candles retention (days)")
    candles_5m_retention: int = Field(default=30, description="5m candles retention (days)")
    candles_15m_retention: int = Field(default=90, description="15m candles retention (days)")
    orderbook_retention: int = Field(default=7, description="Orderbook retention (days)")
    trades_retention: int = Field(default=90, description="Trades retention (days)")
    trader_positions_retention: int = Field(
        default=30, description="Trader positions retention (days)"
    )
    trader_orders_retention: int = Field(default=90, description="Trader orders retention (days)")
    signals_retention: int = Field(default=90, description="Signals retention (days)")

    # =========================================================================
    # Trader Tracking
    # =========================================================================
    max_tracked_traders: int = Field(default=500, description="Maximum traders to track")
    trader_min_score: float = Field(default=50.0, description="Minimum score to track trader")
    trader_selection_interval: int = Field(
        default=86400, description="Trader selection interval (daily)"
    )
    trader_concurrency_limit: int = Field(default=10, description="Concurrent trader API calls")
    trader_ws_connections: int = Field(
        default=10, description="Concurrent WebSocket connections for trader data"
    )
    trader_ws_timeout: float = Field(
        default=3.0, description="WebSocket timeout per trader (seconds)"
    )
    trader_ws_delay_min: float = Field(
        default=0.1, description="Minimum delay between WS requests (seconds)"
    )
    trader_ws_delay_max: float = Field(
        default=0.3, description="Maximum delay between WS requests (seconds)"
    )

    # =========================================================================
    # Archive Configuration
    # =========================================================================
    archive_enabled: bool = Field(default=True, description="Enable archiving")
    archive_base_path: str = Field(default="./archive", description="Archive base directory")
    archive_interval: int = Field(default=86400, description="Archive run interval (daily)")

    # =========================================================================
    # Logging
    # =========================================================================
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(default="logs/hyperliquid.log", description="Log file path")
    log_rotation: str = Field(default="100 MB", description="Log rotation size")
    log_retention: str = Field(default="30 days", description="Log retention period")

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    api_rate_limit: int = Field(default=30, description="API rate limit (requests/second)")
    api_retry_attempts: int = Field(default=3, description="API retry attempts")
    api_retry_delay: float = Field(default=1.0, description="API retry delay (seconds)")
    api_timeout: float = Field(default=30.0, description="API timeout (seconds)")

    # =========================================================================
    # WebSocket Configuration
    # =========================================================================
    websocket_enabled: bool = Field(default=True, description="Enable WebSocket for real-time data")
    websocket_reconnect: bool = Field(
        default=True, description="Auto-reconnect on WebSocket disconnect"
    )
    websocket_reconnect_delay: float = Field(
        default=5.0, description="WebSocket reconnect delay (seconds)"
    )
    websocket_max_reconnect_attempts: int = Field(
        default=10, description="Max WebSocket reconnect attempts"
    )

    # =========================================================================
    # Position Inference (Leaderboard-Only Filtering)
    # =========================================================================
    position_inference_enabled: bool = Field(
        default=True, description="Enable leaderboard-only position inference filtering"
    )
    position_day_roi_threshold: float = Field(
        default=0.0001, description="Day ROI threshold for position inference (0.0001 = 0.01%)"
    )
    position_day_pnl_threshold: float = Field(
        default=0.001, description="Day PnL / AccountValue threshold (0.001 = 0.1%)"
    )
    position_day_volume_threshold: float = Field(
        default=100000.0, description="Minimum day volume to infer position ($)"
    )

    # =========================================================================
    # Persistent Trader WebSocket Manager
    # =========================================================================
    trader_ws_enabled: bool = Field(
        default=True, description="Enable persistent trader WebSocket manager"
    )
    trader_ws_clients: int = Field(default=5, description="Number of persistent WebSocket clients")
    trader_ws_heartbeat: int = Field(
        default=30, description="WebSocket heartbeat interval (seconds)"
    )
    trader_ws_reconnect_delay: float = Field(
        default=5.0, description="Reconnect delay after disconnect (seconds)"
    )
    trader_ws_reconnect_max_delay: float = Field(
        default=60.0, description="Maximum reconnect delay (seconds)"
    )
    trader_ws_reconnect_attempts: int = Field(
        default=10, description="Maximum reconnection attempts"
    )
    trader_ws_batch_size: int = Field(default=100, description="Traders per WebSocket client")
    trader_ws_message_buffer_size: int = Field(
        default=1000, description="Max messages in buffer before processing"
    )
    trader_ws_flush_interval: float = Field(
        default=5.0, description="Interval to flush position updates to DB (seconds)"
    )

    # =========================================================================
    # Persistent Trader Orders WebSocket Manager
    # =========================================================================
    trader_orders_ws_enabled: bool = Field(
        default=True, description="Enable persistent trader orders WebSocket manager"
    )
    trader_orders_ws_flush_interval: float = Field(
        default=5.0, description="Interval to flush order updates to DB (seconds)"
    )

    # =========================================================================
    # Trading Configuration
    # =========================================================================
    target_coin: str = Field(default="BTC", description="Target coin for trading")
    candle_intervals: List[str] = Field(
        default=["1m", "5m", "15m", "1h", "4h", "1d"],
        description="Candle intervals to collect",
    )

    @field_validator("candle_intervals", mode="before")
    @classmethod
    def parse_candle_intervals(cls, v):
        """Parse candle intervals from string or list."""
        if isinstance(v, str):
            # Handle JSON-like string
            v = v.strip("[]").replace('"', "").replace("'", "")
            return [interval.strip() for interval in v.split(",")]
        return v

    # =========================================================================
    # Data Storage Optimization
    # =========================================================================

    # Orderbook Storage - Save only on significant price changes
    orderbook_price_change_threshold_pct: float = Field(
        default=1.0, description="Save orderbook when price changes more than this percentage"
    )
    orderbook_max_save_interval: int = Field(
        default=600, description="Maximum seconds between orderbook saves (safety net)"
    )

    # Trade Filtering - Skip small trades
    trade_min_value_usd: float = Field(
        default=1000.0, description="Minimum trade value in USD to store"
    )

    # Position Updates - Event-driven with safety
    position_change_threshold_pct: float = Field(
        default=0.01, description="Save position when it changes more than this percentage"
    )
    position_only_btc: bool = Field(
        default=True, description="Only save BTC positions (ignore other coins)"
    )
    position_max_save_interval: int = Field(
        default=600, description="Maximum seconds between position saves (safety net)"
    )

    # Signal Generation Frequency (optimized from 30s to 300s)
    signals_interval: int = Field(
        default=300, description="Signal generation interval in seconds (5 minutes)"
    )

    # =========================================================================
    # Computed Properties
    # =========================================================================

    @property
    def retention_config(self) -> dict:
        """Get retention configuration as a dictionary."""
        return {
            "btc_candles_1m": 7,  # Changed from candles_1m_retention to 7 days
            "btc_candles_5m": self.candles_5m_retention,
            "btc_candles_15m": self.candles_15m_retention,
            "btc_orderbook": self.orderbook_retention,
            "btc_trades": self.trades_retention,
            "trader_positions": self.trader_positions_retention,
            "trader_orders": self.trader_orders_retention,
            "btc_signals": self.signals_retention,
        }

    @property
    def interval_config(self) -> dict:
        """Get interval configuration as a dictionary."""
        return {
            "candles": self.candles_interval,
            "orderbook": self.orderbook_interval,
            "trades": self.trades_interval,
            "ticker": self.ticker_interval,
            "funding": self.funding_interval,
            "trader_positions": self.trader_positions_interval,
            "trader_orders": self.trader_orders_interval,
            "signals": self.signals_interval,
        }


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Export settings instance
settings = get_settings()
