#!/usr/bin/env python3
"""
Hyperliquid WebSocket Test Client
Tests orderUpdates and webData2 subscriptions
"""

import asyncio
import aiohttp
import json
import signal
import sys
from datetime import datetime
from typing import Any

WS_URL = "wss://api.hyperliquid.xyz/ws"
TEST_ADDRESS = "0xc28e23e7d7d6cc0c9c6f08146c71e7d168cae45a"  # User provided - has open orders


class HyperliquidWSClient:
    def __init__(self, ws_url: str, address: str, timeout: int = 60):
        self.ws_url = ws_url
        self.address = address
        self.timeout = timeout
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None
        self.messages_received = {"orderUpdates": [], "webData2": [], "other": []}
        self.subscription_confirmed = {"orderUpdates": False, "webData2": False}
        self.running = False
        self.start_time: datetime | None = None

    def _log(self, message: str, level: str = "INFO"):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level_colors = {
            "INFO": "\033[94m",  # Blue
            "SUCCESS": "\033[92m",  # Green
            "WARNING": "\033[93m",  # Yellow
            "ERROR": "\033[91m",  # Red
            "DATA": "\033[96m",  # Cyan
        }
        reset = "\033[0m"
        color = level_colors.get(level, "")
        print(f"[{timestamp}] {color}[{level}]{reset} {message}")

    def _format_json(self, data: Any) -> str:
        """Pretty print JSON data"""
        return json.dumps(data, indent=2)

    async def connect(self):
        """Establish WebSocket connection"""
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(self.ws_url, heartbeat=30.0, autoping=True)
            self._log(f"Connected to {self.ws_url}", "SUCCESS")
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}", "ERROR")
            return False

    async def subscribe_order_updates(self):
        """Subscribe to orderUpdates channel"""
        if not self.ws:
            return False

        subscription = {
            "method": "subscribe",
            "subscription": {"type": "orderUpdates", "user": self.address},
        }

        try:
            await self.ws.send_json(subscription)
            self._log(f"Subscribed to orderUpdates for {self.address}")
            return True
        except Exception as e:
            self._log(f"Subscription failed: {e}", "ERROR")
            return False

    async def subscribe_web_data2(self):
        """Subscribe to webData2 channel"""
        if not self.ws:
            return False

        subscription = {
            "method": "subscribe",
            "subscription": {"type": "webData2", "user": self.address},
        }

        try:
            await self.ws.send_json(subscription)
            self._log(f"Subscribed to webData2 for {self.address}")
            return True
        except Exception as e:
            self._log(f"Subscription failed: {e}", "ERROR")
            return False

    def _classify_message(self, data: dict) -> str:
        """Classify message by channel type"""
        if "channel" in data:
            channel = data["channel"]
            if channel == "orderUpdates":
                return "orderUpdates"
            elif channel == "webData2":
                return "webData2"
            elif channel == "subscriptionResponse":
                # Check for subscription confirmation
                response_data = data.get("data", {})
                if response_data.get("method") == "subscribe":
                    subscription = response_data.get("subscription", {})
                    sub_type = subscription.get("type", "")
                    if sub_type == "orderUpdates":
                        self.subscription_confirmed["orderUpdates"] = True
                        return "subscription_confirm"
                    elif sub_type == "webData2":
                        self.subscription_confirmed["webData2"] = True
                        return "subscription_confirm"
                return "subscription_confirm"

        return "other"

    async def _handle_message(self, msg: aiohttp.WSMessage):
        """Process incoming WebSocket message"""
        if msg.type == aiohttp.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                msg_type = self._classify_message(data)

                if msg_type == "subscription_confirm":
                    response_data = data.get("data", {})
                    subscription = response_data.get("subscription", {})
                    channel = subscription.get("type", "unknown")
                    self._log(f"Subscription confirmed: {channel}", "SUCCESS")

                elif msg_type == "orderUpdates":
                    self.messages_received["orderUpdates"].append(data)
                    self._log(
                        f"Received orderUpdates (total: {len(self.messages_received['orderUpdates'])})",
                        "DATA",
                    )
                    # Show sample structure on first message
                    if len(self.messages_received["orderUpdates"]) == 1:
                        self._log("Sample orderUpdates structure:")
                        print("─" * 60)
                        print(
                            self._format_json(data)[:1000] + "..."
                            if len(self._format_json(data)) > 1000
                            else self._format_json(data)
                        )
                        print("─" * 60)

                elif msg_type == "webData2":
                    self.messages_received["webData2"].append(data)
                    self._log(
                        f"Received webData2 (total: {len(self.messages_received['webData2'])})",
                        "DATA",
                    )
                    # Check for open orders
                    open_orders = data.get("data", {}).get("openOrders", [])
                    if open_orders:
                        self._log(f"🎯 FOUND {len(open_orders)} OPEN ORDERS!", "SUCCESS")
                        self._log("Open Orders:")
                        print("═" * 60)
                        for order in open_orders:
                            print(f"  Coin: {order.get('coin')}")
                            print(f"  Side: {order.get('side')}")
                            print(f"  Price: {order.get('limitPx')}")
                            print(f"  Size: {order.get('sz')}")
                            print(f"  OID: {order.get('oid')}")
                            print("-" * 40)
                        print("═" * 60)

                    # Show sample structure on first message
                    if len(self.messages_received["webData2"]) == 1:
                        self._log("Sample webData2 structure:")
                        print("─" * 60)
                        # Show full data but truncate positions
                        sample_data = data.copy()
                        if "data" in sample_data and "clearinghouseState" in sample_data["data"]:
                            if "assetPositions" in sample_data["data"]["clearinghouseState"]:
                                positions = sample_data["data"]["clearinghouseState"][
                                    "assetPositions"
                                ]
                                sample_data["data"]["clearinghouseState"]["assetPositions"] = (
                                    f"[{len(positions)} positions]"
                                )
                        print(self._format_json(sample_data))
                        print("─" * 60)

                else:
                    self.messages_received["other"].append(data)
                    self._log(f"Received other message: {self._format_json(data)[:200]}", "WARNING")

            except json.JSONDecodeError as e:
                self._log(f"Failed to parse message: {e}", "ERROR")
                self._log(f"Raw data: {msg.data[:200]}...", "WARNING")

        elif msg.type == aiohttp.WSMsgType.ERROR:
            self._log(f"WebSocket error: {msg.data}", "ERROR")

        elif msg.type == aiohttp.WSMsgType.CLOSED:
            self._log("WebSocket connection closed", "WARNING")

    async def listen(self):
        """Listen for messages with timeout"""
        if not self.ws:
            return

        self.running = True
        self.start_time = datetime.now()

        async def _listen_loop():
            async for msg in self.ws:
                if not self.running:
                    break
                await self._handle_message(msg)

        try:
            await asyncio.wait_for(_listen_loop(), timeout=self.timeout)
        except asyncio.TimeoutError:
            self._log(f"Test completed after {self.timeout} seconds", "SUCCESS")
        except Exception as e:
            self._log(f"Error during listening: {e}", "ERROR")

    async def close(self):
        """Clean up resources"""
        self.running = False

        if self.ws and not self.ws.closed:
            await self.ws.close()
            self._log("WebSocket closed")

        if self.session and not self.session.closed:
            await self.session.close()
            self._log("Session closed")

    def print_summary(self):
        """Print test summary"""
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        print("\n" + "=" * 70)
        print("                    HYPERLIQUID WEBSOCKET TEST SUMMARY")
        print("=" * 70)
        print(f"Test Address:     {self.address}")
        print(f"Duration:         {duration:.1f} seconds")
        print()

        print("Subscription Status:")
        print(
            f"  orderUpdates:   {'✅ CONFIRMED' if self.subscription_confirmed['orderUpdates'] else '❌ NOT CONFIRMED'}"
        )
        print(
            f"  webData2:       {'✅ CONFIRMED' if self.subscription_confirmed['webData2'] else '❌ NOT CONFIRMED'}"
        )
        print()

        print("Messages Received:")
        print(f"  orderUpdates:   {len(self.messages_received['orderUpdates'])}")
        print(f"  webData2:       {len(self.messages_received['webData2'])}")
        print(f"  other:          {len(self.messages_received['other'])}")
        print()

        print("=" * 70)
        print("                          CONCLUSION")
        print("=" * 70)

        if self.subscription_confirmed["orderUpdates"]:
            if len(self.messages_received["orderUpdates"]) > 0:
                print("✅ orderUpdates subscription WORKS and received data!")
                print(f"   Received {len(self.messages_received['orderUpdates'])} order update(s)")
            else:
                print("⚠️  orderUpdates subscription confirmed but no order data received")
                print("   This is expected if the test address has no active orders")
        else:
            print("❌ orderUpdates subscription NOT confirmed")
            print("   The subscription request may have failed or response was unexpected")

        print()

        if self.subscription_confirmed["webData2"]:
            if len(self.messages_received["webData2"]) > 0:
                print("✅ webData2 subscription WORKS and received data!")
                print(f"   Received {len(self.messages_received['webData2'])} webData2 update(s)")
            else:
                print("⚠️  webData2 subscription confirmed but no data received")
        else:
            print("❌ webData2 subscription NOT confirmed")

        print("=" * 70)


async def main():
    """Main test function"""
    client = HyperliquidWSClient(WS_URL, TEST_ADDRESS, timeout=60)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n")
        client._log("Received interrupt signal, shutting down...", "WARNING")
        client.running = False

    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Connect
        if not await client.connect():
            print("\n❌ Failed to connect to WebSocket")
            return 1

        # Subscribe to channels
        await client.subscribe_order_updates()
        await asyncio.sleep(0.5)  # Small delay between subscriptions
        await client.subscribe_web_data2()

        # Listen for messages
        client._log(f"Listening for messages (timeout: {client.timeout}s)...")
        client._log("Press Ctrl+C to stop early\n")
        await client.listen()

    except KeyboardInterrupt:
        client._log("Interrupted by user", "WARNING")
    except Exception as e:
        client._log(f"Unexpected error: {e}", "ERROR")
    finally:
        await client.close()
        client.print_summary()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
