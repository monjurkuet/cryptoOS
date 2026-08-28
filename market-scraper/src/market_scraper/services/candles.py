"""BTC candle fetcher and price service — uses Kraken + Hyperliquid + Coingecko fallbacks."""
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Kraken intervals: 1,5,15,60,240,1440
KRAKEN_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
HL_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}

def _req_json(url: str, timeout: int = 15) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)

async def fetch_kraken_candles(interval: str = "1h", limit: int = 100) -> list[dict[str, Any]]:
    """Fetch OHLC from Kraken (no proxy needed)."""
    kraken_interval = KRAKEN_INTERVALS.get(interval, 60)
    url = f"https://api.kraken.com/0/public/OHLC?pair=BTCUSD&interval={kraken_interval}"
    import asyncio
    def _fetch():
        payload = _req_json(url)
        if payload.get("error"):
            raise RuntimeError(f"Kraken error: {payload['error']}")
        result = payload["result"]
        key = next(k for k in result if k != "last")
        rows = result[key][-limit:]
        out = []
        for r in rows:
            out.append({
                "t": datetime.fromtimestamp(int(r[0]), tz=UTC),
                "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
                "close": float(r[4]), "volume": float(r[6]),
                "interval": interval, "source": "kraken"
            })
        return out
    return await asyncio.to_thread(_fetch)

async def fetch_coingecko_price() -> dict[str, Any]:
    import asyncio
    def _fetch():
        data = _req_json("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        return data
    data = await asyncio.to_thread(_fetch)
    price = float(data["bitcoin"]["usd"])
    return {"price": price, "symbol": "BTC", "source": "coingecko", "timestamp": datetime.now(UTC).isoformat()}

async def fetch_kraken_price() -> dict[str, Any]:
    import asyncio
    def _fetch():
        data = _req_json("https://api.kraken.com/0/public/Ticker?pair=BTCUSD")
        price = float(data["result"]["XXBTZUSD"]["c"][0])
        return price
    price = await asyncio.to_thread(_fetch)
    return {"price": price, "symbol": "BTC", "source": "kraken", "timestamp": datetime.now(UTC).isoformat()}

async def get_btc_price() -> dict[str, Any]:
    """Try Kraken -> Coingecko fallback."""
    try:
        return await fetch_kraken_price()
    except Exception as e:
        logger.warning("kraken_price_failed", error=str(e))
        return await fetch_coingecko_price()
