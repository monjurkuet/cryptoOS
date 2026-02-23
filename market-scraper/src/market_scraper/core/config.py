# src/market_scraper/core/config.py

"""Configuration management for the Market Scraper Framework."""

from functools import lru_cache

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    url: str = Field(default="redis://localhost:6379")
    max_connections: int = Field(default=10)
    socket_timeout: float = Field(default=5.0)
    socket_connect_timeout: float = Field(default=5.0)


class MongoConfig(BaseModel):
    """MongoDB connection configuration."""

    url: str = Field(default="mongodb://localhost:27017")
    database: str = Field(default="market_scraper")
    max_pool_size: int = Field(default=10)
    min_pool_size: int = Field(default=1)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO")
    format: str = Field(default="json")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()


class HyperliquidSettings(BaseModel):
    """Hyperliquid connector settings."""

    enabled: bool = Field(default=True, description="Whether Hyperliquid connector is enabled")
    api_url: str = Field(default="https://api.hyperliquid.xyz", description="Hyperliquid API URL")
    ws_url: str = Field(default="wss://api.hyperliquid.xyz/ws", description="WebSocket URL")
    api_key: str | None = Field(default=None, description="Optional API key")

    # Symbol configuration - ONLY this symbol's data is saved to DB
    symbol: str = Field(
        default="BTC", description="Symbol to track (only this symbol's data is saved)"
    )

    # Collector settings
    position_max_interval: int = Field(
        default=600, description="Max interval in seconds between position saves"
    )

    # WebSocket settings
    reconnect_max_attempts: int = Field(default=10, description="Max reconnection attempts")
    reconnect_base_delay: float = Field(
        default=1.0, description="Base delay for exponential backoff"
    )
    reconnect_max_delay: float = Field(
        default=30.0, description="Max delay for exponential backoff"
    )
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")

    # Rate limiting
    rate_limit_per_second: float = Field(default=10.0, description="Rate limit for API requests")
    timeout_seconds: float = Field(default=30.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Max retries for failed requests")
    retry_delay_seconds: float = Field(default=1.0, description="Delay between retries")


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="market-scraper")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")

    # Redis
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # MongoDB
    mongo: MongoConfig = Field(default_factory=MongoConfig)

    # Logging
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Hyperliquid connector settings
    hyperliquid: HyperliquidSettings = Field(default_factory=HyperliquidSettings)

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
