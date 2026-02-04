# Hyperliquid WebSocket API

## WebSocket Endpoint
```
wss://api.hyperliquid.xyz/trading
```

## Subscription Message Format
```json
{
  "type": "subscribe",
  "subscription": {
    "type": "trades",
    "coin": "BTC"
  }
}
```

## Available Channels

### Public Channels

| Channel | Description | Parameters |
|---------|-------------|------------|
| `trades` | Real-time trades | `coin` |
| `book` | Orderbook updates | `coin` |
| `candle` | OHLC candles | `coin`, `interval` |
| `webData2` | General updates | - |

### Private Channels (Requires Authentication)

| Channel | Description |
|---------|-------------|
| `orderUpdates` | Order status updates |
| `userFills` | User trade notifications |
| `user` | User state changes |

## Subscription Examples

### Subscribe to BTC Trades
```json
{
  "type": "subscribe",
  "subscription": {
    "type": "trades",
    "coin": "BTC"
  }
}
```

### Subscribe to Orderbook
```json
{
  "type": "subscribe",
  "subscription": {
    "type": "book",
    "coin": "ETH"
  }
}
```

### Subscribe to Candles
```json
{
  "type": "subscribe",
  "subscription": {
    "type": "candle",
    "coin": "SOL",
    "interval": "1h"
  }
}
```

### Unsubscribe
```json
{
  "type": "unsubscribe",
  "subscription": {
    "type": "trades",
    "coin": "BTC"
  }
}
```

## Usage with Python

```python
import asyncio
import websockets

async def subscribe():
    async with websockets.connect("wss://api.hyperliquid.xyz/trading") as ws:
        # Subscribe to trades
        await ws.send('{"type":"subscribe","subscription":{"type":"trades","coin":"BTC"}}')
        
        # Receive messages
        async for msg in ws:
            print(msg)

asyncio.run(subscribe())
```

## Usage with Bash (websocat)
```bash
websocat -E -B 65535 wss://api.hyperliquid.xyz/trading \
  --text '{"type":"subscribe","subscription":{"type":"trades","coin":"BTC"}}'
```

## Interval Options

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `1h` | 1 hour |
| `4h` | 4 hours |
| `1d` | 1 day |

## Rate Limits

- Maximum 30 requests per second
- Maximum 100 subscriptions per connection
- Connections may be rate limited

## Use Cases

- Real-time price updates
- Live orderbook tracking
- Instant trade notifications
- Portfolio value monitoring

## Data Source

Hyperliquid Official WebSocket API (api.hyperliquid.xyz)
