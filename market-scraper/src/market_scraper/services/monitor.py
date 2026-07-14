"""Serial WebSocket position monitor — 5 traders at a time."""
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

import structlog
import websockets

from market_scraper.config import get_settings
from market_scraper.db import get_db

logger = structlog.get_logger(__name__)


class PositionMonitor:
    """Single WebSocket, 5 traders per batch, 60s dwell, ascending ROI order."""

    def __init__(self):
        self.settings = get_settings()
        self._running = True

    async def run_forever(self) -> None:
        """Main loop: fetch tracked traders, cycle through batches."""
        while self._running:
            try:
                db = get_db()
                # Ascending ROI: lowest first, highest last
                # Highest-ROI traders get sampled most frequently (cycle restarts)
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
        """Connect WS, subscribe, listen for dwell seconds, store positions."""
        addresses = [t["eth"].lower() for t in traders if t.get("eth")]
        if not addresses:
            return

        symbol = self.settings.monitor.symbol.upper()

        try:
            async with websockets.connect(
                self.settings.monitor.ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                # Subscribe all traders in batch
                for addr in addresses:
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "webData2", "user": addr},
                    }))
                    await asyncio.sleep(0.05)

                logger.info("monitor_batch_subscribed", addresses=len(addresses))

                # Listen for dwell seconds
                end_time = time.monotonic() + self.settings.monitor.dwell_seconds
                messages = 0
                while time.monotonic() < end_time:
                    try:
                        remaining = end_time - time.monotonic()
                        msg = await asyncio.wait_for(ws.recv(), timeout=min(1.0, max(0.1, remaining)))
                        await self._handle_message(msg, symbol)
                        messages += 1
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break

                # Clean unsubscribe before closing
                for addr in addresses:
                    try:
                        await ws.send(json.dumps({
                            "method": "unsubscribe",
                            "subscription": {"type": "webData2", "user": addr},
                        }))
                    except Exception:
                        pass

                logger.info("monitor_batch_complete", messages=messages)

        except Exception as e:
            logger.error("monitor_batch_error", error=str(e))

    async def _handle_message(self, msg: str, symbol: str) -> None:
        """Parse webData2, normalize, dedup, store to MongoDB."""
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            return

        if data.get("channel") != "webData2":
            return

        payload = data.get("data", {})
        if not isinstance(payload, dict):
            return

        eth = str(payload.get("user", "")).lower()
        if not eth:
            return

        ch = payload.get("clearinghouseState", {})
        if not isinstance(ch, dict):
            return

        # Filter to configured symbol only
        raw_positions = ch.get("assetPositions", [])
        if not isinstance(raw_positions, list):
            raw_positions = []

        positions = []
        for raw_pos in raw_positions:
            pos = raw_pos.get("position", {})
            if not isinstance(pos, dict):
                continue
            if pos.get("coin", "").upper() != symbol:
                continue
            try:
                if float(pos.get("szi", 0)) != 0:
                    positions.append(raw_pos)
            except (TypeError, ValueError):
                pass

        # Open orders for this symbol
        raw_orders = payload.get("openOrders", [])
        if not isinstance(raw_orders, list):
            raw_orders = []
        open_orders = [
            o for o in raw_orders
            if isinstance(o, dict)
            and o.get("coin", "").upper() == symbol
        ]

        margin_summary = ch.get("marginSummary", {})
        if not isinstance(margin_summary, dict):
            margin_summary = {}

        # Hash for dedup
        pos_str = json.dumps(positions, sort_keys=True, separators=(",", ":"))
        ord_str = json.dumps(open_orders, sort_keys=True, separators=(",", ":"))
        marg_str = json.dumps(margin_summary, sort_keys=True, separators=(",", ":"))
        position_hash = hashlib.sha256(
            (pos_str + ord_str + marg_str).encode()
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
                "open_orders": open_orders,
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

        # Update tracked trader's last position timestamp
        await db.tracked_traders.update_one(
            {"eth": eth},
            {"$set": {"last_position_update": now, "position_hash": position_hash}},
        )


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
