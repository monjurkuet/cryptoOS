"""Signal System Configuration."""

import os
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).parents[3]  # cryptoOS/


class RedisSettings(BaseSettings):
    """Redis configuration.

    The channel_prefix must be "events" to match the market-scraper's
    Redis publishing format: "events:{event_type}"
    """

    url: str = Field(default="redis://localhost:6379/0")
    channel_prefix: str = Field(default="events")

    model_config = {"env_prefix": "REDIS_"}


class MongoSettings(BaseSettings):
    """MongoDB configuration for RL outcome storage."""

    url: str = Field(default="mongodb://localhost:27017")
    database: str = Field(default="signal_system")
    market_database: str = Field(default="market_scraper")

    model_config = {"env_prefix": "SIGNAL_MONGO_"}


class SignalSystemSettings(BaseSettings):
    """Main application settings."""

    redis: RedisSettings = Field(default_factory=RedisSettings)
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=4341)
    api_root_path: str = Field(default="/signal-system")
    symbol: str = Field(default="BTC")
    dashboard_retention_days: int = Field(default=30)

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }

    @field_validator("api_root_path", mode="before")
    @classmethod
    def normalize_api_root_path(cls, value: str | None) -> str:
        """Normalize API root path for reverse-proxy deployments."""
        text = (value or "").strip()
        if text in ("", "/"):
            return ""
        if not text.startswith("/"):
            text = f"/{text}"
        return text.rstrip("/")


def get_settings() -> SignalSystemSettings:
    """Get application settings."""
    return SignalSystemSettings()
