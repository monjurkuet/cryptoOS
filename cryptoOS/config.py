from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    data_dir: Path = Path("./data")
    log_level: str = "INFO"
    max_retries: int = 3
    request_timeout: int = 30

    cryptoquant_api_key: Optional[str] = None
    hyperliquid_private_key: Optional[str] = None

    cbbi_base_url: str = "https://colintalkscrypto.com/cbbi/data"
    hyperliquid_api_url: str = "https://api.hyperliquid.xyz/info"
    hyperliquid_ws_url: str = "wss://api.hyperliquid.xyz/trading"
    cryptoquant_graphql_url: str = "https://graph.cryptoquant.com/graphql"
    cryptoquant_api_url: str = "https://api.cryptoquant.com/v1"

    class Config:
        env_file = ".env"
        env_prefix = "CRYPTOOS_"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_dir.mkdir(parents=True, exist_ok=True)
