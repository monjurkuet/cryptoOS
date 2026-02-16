#!/usr/bin/env python3
"""
Compare REST API vs WebSocket for order collection.
Tests with multiple wallets that have open orders.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Dict, List, Any

# Test addresses with known open orders from database
TEST_ADDRESSES = [
    "0x6859da14835424957a1e6b397d8026b1d9ff7e1e",  # Most active - multiple ETH/FARTCOIN orders
    "0x35d1151ef1aab579cbb3109e69fa82f94ff5acb1",  # ETH buyer
    "0xdd7a372377fc633f74ab6e20963803d52f448830",  # VVV seller
]

REST_API_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"


class OrderComparator:
    def __init__(self):
        self.results = {}

    def _log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        colors = {
            "INFO": "\033[94m",
            "SUCCESS": "\033[92m",
            "WARNING": "\033[93m",
            "ERROR": "[91m",
            "DATA": "\033[96m",
        }
        reset = "\033[0m"
        print(f"[{timestamp}] {colors.get(level, '')}[{level}]{reset} {message}")

    async def fetch_rest_orders(self, session: aiohttp.ClientSession, address: str) -> List[Dict]:
        """Fetch orders via REST API"""
        try:
            payload = {"type": "openOrders", "user": address}
            async with session.post(REST_API_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []
                else:
                    self._log(f"REST API error {resp.status} for {address[:20]}...", "ERROR")
                    return []
        except Exception as e:
            self._log(f"REST API exception: {e}", "ERROR")
            return []

    async def fetch_ws_orders(self, address: str) -> List[Dict]:
        """Fetch orders via WebSocket webData2"""
        orders = []

        try:
            session = aiohttp.ClientSession()
            ws = await session.ws_connect(WS_URL, heartbeat=30.0)

            # Subscribe to webData2
            await ws.send_json(
                {"method": "subscribe", "subscription": {"type": "webData2", "user": address}}
            )

            # Wait for subscription confirmation and data
            for _ in range(20):  # Try up to 20 messages
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)

                        if data.get("channel") == "webData2":
                            open_orders = data.get("data", {}).get("openOrders", [])
                            if open_orders:
                                orders = open_orders
                                break
                            else:
                                # Empty openOrders means no active orders
                                orders = []
                                break

                        elif data.get("channel") == "subscriptionResponse":
                            self._log(f"WebSocket subscription confirmed for {address[:20]}...")

                except asyncio.TimeoutError:
                    break

            await ws.close()
            await session.close()

        except Exception as e:
            self._log(f"WebSocket exception: {e}", "ERROR")

        return orders

    def compare_orders(self, address: str, rest_orders: List[Dict], ws_orders: List[Dict]):
        """Compare REST vs WebSocket results"""
        print("\n" + "=" * 70)
        print(f"COMPARISON FOR: {address}")
        print("=" * 70)

        # Normalize orders for comparison
        rest_normalized = set()
        for o in rest_orders:
            key = (o.get("coin"), o.get("side"), float(o.get("limitPx", 0)), float(o.get("sz", 0)))
            rest_normalized.add(key)

        ws_normalized = set()
        for o in ws_orders:
            key = (o.get("coin"), o.get("side"), float(o.get("limitPx", 0)), float(o.get("sz", 0)))
            ws_normalized.add(key)

        print(f"\n📊 REST API Orders: {len(rest_orders)}")
        for o in rest_orders:
            print(
                f"   {o.get('coin'):<8} {o.get('side'):<4} @ {o.get('limitPx'):<12} size: {o.get('sz')}"
            )

        print(f"\n📡 WebSocket Orders: {len(ws_orders)}")
        for o in ws_orders:
            print(
                f"   {o.get('coin'):<8} {o.get('side'):<4} @ {o.get('limitPx'):<12} size: {o.get('sz')}"
            )

        # Check match
        if rest_normalized == ws_normalized:
            print(f"\n✅ PERFECT MATCH! Both sources have identical orders")
        else:
            only_in_rest = rest_normalized - ws_normalized
            only_in_ws = ws_normalized - rest_normalized

            if only_in_rest:
                print(f"\n⚠️  Only in REST ({len(only_in_rest)} orders):")
                for o in only_in_rest:
                    print(f"   {o}")

            if only_in_ws:
                print(f"\n⚠️  Only in WebSocket ({len(only_in_ws)} orders):")
                for o in only_in_ws:
                    print(f"   {o}")

        return len(rest_orders), len(ws_orders)

    async def test_address(self, session: aiohttp.ClientSession, address: str):
        """Test single address"""
        self._log(f"Testing {address[:20]}...")

        # Fetch from both sources concurrently
        rest_task = self.fetch_rest_orders(session, address)
        ws_task = self.fetch_ws_orders(address)

        rest_orders, ws_orders = await asyncio.gather(rest_task, ws_task)

        rest_count, ws_count = self.compare_orders(address, rest_orders, ws_orders)

        return {
            "address": address,
            "rest_count": rest_count,
            "ws_count": ws_count,
            "match": rest_count == ws_count,
        }

    async def run_comparison(self):
        """Run comparison for all test addresses"""
        print("\n" + "=" * 70)
        print("REST API vs WEBSOCKET ORDER COMPARISON")
        print("=" * 70)

        async with aiohttp.ClientSession() as session:
            results = []
            for address in TEST_ADDRESSES:
                result = await self.test_address(session, address)
                results.append(result)
                await asyncio.sleep(1)  # Rate limiting

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for r in results:
            status = "✅ MATCH" if r["match"] else "❌ MISMATCH"
            print(
                f"{r['address'][:30]}... REST: {r['rest_count']:<3} WS: {r['ws_count']:<3} {status}"
            )


async def main():
    comparator = OrderComparator()
    await comparator.run_comparison()


if __name__ == "__main__":
    asyncio.run(main())
