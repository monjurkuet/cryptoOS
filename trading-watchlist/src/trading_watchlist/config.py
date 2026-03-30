"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings."""

    model_config = SettingsConfigDict(env_prefix="TRADING_WATCHLIST_", extra="ignore")

    app_name: str = "Trading Watchlist API"
    app_version: str = "0.1.0"
    trading_data_dir: Path = Field(default=Path("/mnt/vhd/trading"))
    structured_data_dir: Path | None = None
    btc_market_url: str = "http://localhost:3845/api/v1/markets/BTC"

    @property
    def rules_path(self) -> Path:
        return self.trading_data_dir / "analysis-rules.md"

    @property
    def trades_path(self) -> Path:
        return self.trading_data_dir / "analysis-trades.md"

    @property
    def watchlist_path(self) -> Path:
        return self.trading_data_dir / "analysis-watchlist.md"

    @property
    def json_data_dir(self) -> Path:
        return self.structured_data_dir or (self.trading_data_dir / "data")

    @property
    def rules_json_path(self) -> Path:
        return self.json_data_dir / "rules.json"

    @property
    def positions_json_path(self) -> Path:
        return self.json_data_dir / "positions.json"

    @property
    def watchlist_json_path(self) -> Path:
        return self.json_data_dir / "watchlist.json"

    @property
    def prices_json_path(self) -> Path:
        return self.json_data_dir / "prices.json"

    @property
    def state_json_path(self) -> Path:
        return self.json_data_dir / "state.json"

    @property
    def manifest_json_path(self) -> Path:
        return self.json_data_dir / "manifest.json"

    @property
    def generated_rules_path(self) -> Path:
        return self.trading_data_dir / "analysis-rules.generated.md"

    @property
    def generated_trades_path(self) -> Path:
        return self.trading_data_dir / "analysis-trades.generated.md"

    @property
    def generated_watchlist_path(self) -> Path:
        return self.trading_data_dir / "analysis-watchlist.generated.md"

    @property
    def generated_brief_path(self) -> Path:
        return self.trading_data_dir / "analysis-brief.generated.md"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()
