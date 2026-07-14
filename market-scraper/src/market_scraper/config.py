"""Settings loaded from environment variables."""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class LeaderboardConfig(BaseSettings):
    """Hyperliquid leaderboard scoring config (from code defaults)."""

    model_config = SettingsConfigDict(extra="ignore")
    weights: dict[str, float] = {
        "roi_all_time": 30,
        "roi_month": 25,
        "roi_week": 20,
        "account_value": 15,
        "volume_month": 10,
    }
    require_positive: list[str] = ["all_time", "year", "month"]
    max_tracked: int = 1000
    min_account_value: float = 10000.0
    ws_url: str = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


class MonitorConfig(BaseSettings):
    """WS position monitor config (from code defaults)."""

    model_config = SettingsConfigDict(extra="ignore")
    batch_size: int = 5
    dwell_seconds: int = 60
    symbol: str = "BTC"
    ws_url: str = "wss://api.hyperliquid.xyz/ws"
    sort_ascending_by_roi: bool = True
    enable_hash_dedup: bool = True


class Settings(BaseSettings):
    """Application settings. Vars set via env file loaded in get_settings()."""

    model_config = SettingsConfigDict(
        extra="ignore",
        env_ignore_empty=True,
    )

    api_host: str = "127.0.0.1"
    api_port: int = 3845
    log_level: str = "INFO"
    log_format: str = "json"

    # MongoDB — set from MONGO__URL / MONGO__DATABASE in get_settings()
    mongo_url: str = "mongodb+srv://placeholder"
    mongo_db: str = "market_scraper"
    leaderboard_retention_days: int = 365
    position_retention_days: int = 30

    leaderboard: LeaderboardConfig = LeaderboardConfig()
    monitor: MonitorConfig = MonitorConfig()


_settings: Settings | None = None

_ENV_FILE = "/home/administrator/githubrepo/cryptoOS/.env"


def _load_env() -> None:
    """Load .env into os.environ if not already present."""
    global _ENV_FILE
    if not os.path.exists(_ENV_FILE):
        return
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def get_settings() -> Settings:
    """Settings singleton. Loads .env on first call."""
    global _settings
    if _settings is None:
        _load_env()
        s = Settings()
        # Map MONGO__URL → mongo_url (pydantic can't parse double-underscore)
        env_url = os.environ.get("MONGO__URL") or os.environ.get("SIGNAL_MONGO__URL", "")
        if env_url and "placeholder" not in env_url:
            s.mongo_url = env_url
        env_db = os.environ.get("MONGO__DATABASE", "")
        if env_db:
            s.mongo_db = env_db
        _settings = s
    return _settings
