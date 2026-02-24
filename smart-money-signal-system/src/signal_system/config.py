"""Signal System Configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings


class RedisSettings(BaseSettings):
    """Redis configuration.

    The channel_prefix must be "events" to match the market-scraper's
    Redis publishing format: "events:{event_type}"
    """

    url: str = Field(default="redis://localhost:6379/0")
    channel_prefix: str = Field(default="events")

    model_config = {"env_prefix": "REDIS_"}


class SignalSystemSettings(BaseSettings):
    """Main application settings."""

    redis: RedisSettings = Field(default_factory=RedisSettings)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=4341)
    symbol: str = Field(default="BTC")

    model_config = {"env_file": ".env", "env_nested_delimiter": "__", "extra": "ignore"}


def get_settings() -> SignalSystemSettings:
    """Get application settings."""
    return SignalSystemSettings()
