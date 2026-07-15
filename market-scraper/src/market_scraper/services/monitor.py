"""Serial REST position monitor — polls clearinghouseState for each trader."""
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from market_scraper.config import get_settings
from market_scraper.db import get_db

logger = structlog.get_logger(__name__)

CLEARINGHOUSE_URL = "https://api.hyperliquid.xyz/info"


class PositionMonitor:
    """REST polling: 5 traders at a time, 60s dwell, ascending ROI order."""

    def __init__(self):
        self.settings = get_settings()
        self._running = True

    async def run_forever(self) -> None:
        """Main loop: fetch tracked traders, poll positions."""
        while self._running:
            try:
                db = get_db()
                # Ascending ROI: lowest first, highest last
                cursor = db.tracked_traders.find({}).sort("roi_all_time", 1)
                traders = await cursor.to_list(length=1000)

                if not traders:
                    logger.info("monitor_no_traders")
                    await asyncio.sleep(300)
                    continue

                batch_size = self.settings.monitor.batch_size
                logger.info("monitor_cycle_start", total=len(traders))

                for i in range(0, len(traders), batch_size):
                    if not self._running:
                        break
                    batch = traders[i : i + batch_size]
                    await self._process_batch(batch)

                logger.info("monitor_cycle_complete")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitor_cycle_error", error=str(e))
                await asyncio.sleep(30)

    def stop(self) -> None:
        self._running = False

    async def _process_batch(self, traders: list[dict[str, Any]]) -> None:
        """Poll clearinghouseState for each trader, store positions."""
        symbol = self.settings.monitor.symbol.upper()

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                for trader in traders:
                    if not self._running:
                        break
                    addr = trader.get("eth", "").lower()
                    if not addr:
                        continue

                    try:
                        resp = await client.post(
                            CLEARINGHOUSE_URL,
                            json={"type": "clearinghouseState", "user": addr},
                        )
                        if resp.status_code != 200:
                            continue
                        data = resp.json()
                        await self._store_state(addr, data, symbol)
                    except httpx.HTTPError as e:
                        logger.warning("monitor_poll_error", addr=addr[:10], error=str(e))
                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)

            # Dwell between batches
            await asyncio.sleep(max(1, self.settings.monitor.dwell_seconds - 0.5))

        except Exception as e:
            logger.error("monitor_batch_error", error=str(e))

    async def _store_state(self, eth: str, data: dict[str, Any], symbol: str) -> None:
        """Parse clearinghouseState, dedup, store to MongoDB."""
        # Filter positions to configured symbol only
        raw_positions = data.get("assetPositions", [])
        if not isinstance(raw_positions, list):
            raw_positions = []

        positions = [
            p for p in raw_positions
            if isinstance(p, dict)
            and p.get("position", {}).get("coin", "").upper() == symbol
            and float(p.get("position", {}).get("szi", 0) or 0) != 0
        ]

        margin_summary = data.get("marginSummary", {})
        if not isinstance(margin_summary, dict):
            margin_summary = {}

        # Hash for dedup
        pos_str = json.dumps(positions, sort_keys=True, separators=(",", ":"))
        marg_str = json.dumps(margin_summary, sort_keys=True, separators=(",", ":"))
        position_hash = hashlib.sha256(
            (pos_str + marg_str).encode()
        ).hexdigest()

        # Dedup check
        if self.settings.monitor.enable_hash_dedup:
            db = get_db()
            existing = await db.trader_current_state.find_one({"eth": eth})
            if existing and existing.get("position_hash") == position_hash:
                return  # No change

        now = datetime.now(UTC)
        db = get_db()

        # Store current state (upsert)
        await db.trader_current_state.update_one(
            {"eth": eth},
            {"$set": {
                "eth": eth,
                "symbol": symbol,
                "positions": positions,
                "margin_summary": margin_summary,
                "position_hash": position_hash,
                "updated_at": now,
            }},
            upsert=True,
        )

        # Store position history (append for time-series queries)
        for raw_pos in positions:
            pos = raw_pos.get("position", {})
            await db.trader_positions.insert_one({
                "eth": eth,
                "symbol": symbol,
                "size": float(pos.get("szi", 0) or 0),
                "entry_price": float(pos.get("entryPx", 0) or 0),
                "mark_price": float(pos.get("markPx", 0) or 0),
                "unrealized_pnl": float(pos.get("unrealizedPnl", 0) or 0),
                "leverage": _parse_leverage(pos.get("leverage")),
                "liquidation_price": _parse_float_or_none(pos.get("liquidationPx")),
                "t": now,
            })

        # Update tracked trader
        await db.tracked_traders.update_one(
            {"eth": eth},
            {"$set": {"last_position_update": now, "position_hash": position_hash}},
        )

        logger.debug("monitor_stored", addr=eth[:10], positions=len(positions), hash=position_hash[:16])


def _parse_leverage(val: Any) -> float:
    if isinstance(val, dict):
        return float(val.get("value", 0) or 0)
    return float(val or 0)


def _parse_float_or_none(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
