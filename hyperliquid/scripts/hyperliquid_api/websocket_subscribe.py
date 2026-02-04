#!/usr/bin/env python3
"""
Hyperliquid WebSocket Client

Subscribe to real-time data from Hyperliquid exchange.

Usage:
    python3 websocket_subscribe.py <channel> <coin>
    python3 websocket_subscribe.py trades BTC
    python3 websocket_subscribe.py book BTC
    python3 websocket_subscribe.py candle BTC 1h
"""

import asyncio
import json
import sys
import websockets

WEBSOCKET_URL = "wss://api.hyperliquid.xyz/trading"


def get_subscribe_message(channel, coin=None, interval=None):
    """Generate subscription message based on channel type."""
    if channel == "trades":
        return {"type": "subscribe", "subscription": {"type": "trades", "coin": coin}}
    elif channel == "book":
        return {"type": "subscribe", "subscription": {"type": "book", "coin": coin}}
    elif channel == "candle":
        return {
            "type": "subscribe",
            "subscription": {"type": "candle", "coin": coin, "interval": interval},
        }
    elif channel == "orderUpdates":
        return {"type": "subscribe", "subscription": {"type": "orderUpdates"}}
    elif channel == "userFills":
        return {"type": "subscribe", "subscription": {"type": "userFills"}}
    elif channel == "user":
        return {"type": "subscribe", "subscription": {"type": "user"}}
    elif channel == "webData2":
        return {"type": "subscribe", "subscription": {"type": "webData2"}}
    else:
        raise ValueError(f"Unknown channel: {channel}")


async def subscribe(channel, coin=None, interval=None):
    """Subscribe to WebSocket channel and print messages."""
    msg = get_subscribe_message(channel, coin, interval)
    print(f"Connecting to {WEBSOCKET_URL}...")
    print(f"Subscribing to: {msg}")

    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            await websocket.send(json.dumps(msg))

            count = 0
            max_messages = int(sys.argv[3]) if len(sys.argv) > 3 else 10

            async for message in websocket:
                data = json.loads(message)
                print(json.dumps(data, indent=2))
                count += 1

                if count >= max_messages:
                    print(f"\nReceived {count} messages, stopping...")
                    break

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nAvailable channels:")
        print("  trades       - Recent trades")
        print("  book         - Order book")
        print("  candle       - OHLC candles")
        print("  orderUpdates - Order updates (requires auth)")
        print("  userFills    - User fills (requires auth)")
        print("  user         - User state (requires auth)")
        print("  webData2     - Web data subscription")
        sys.exit(1)

    channel = sys.argv[1]
    coin = sys.argv[2] if len(sys.argv) > 2 else None
    interval = sys.argv[3] if len(sys.argv) > 3 else "1h"

    asyncio.run(subscribe(channel, coin, interval))
