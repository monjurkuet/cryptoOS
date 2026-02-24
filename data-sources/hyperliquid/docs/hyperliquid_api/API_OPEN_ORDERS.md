# Hyperliquid Open Orders API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "openOrders",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns all currently open (pending) orders for a user.

## Response Format
```json
[
  {
    "coin": "BTC",
    "side": "B",
    "limitPx": "75608.0",
    "sz": "1.3918",
    "oid": 311059973866,
    "timestamp": 1770163571395,
    "origSz": "1.3918",
    "cloid": "0x00158af8259c01000000000000000000"
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | string | Perpetual coin ticker |
| `side` | string | Order side: "B" (Buy) or "A" (Ask/Sell) |
| `limitPx` | string | Limit price |
| `sz` | string | Current order size |
| `oid` | number | Order ID |
| `timestamp` | number | Order creation timestamp (milliseconds) |
| `origSz` | string | Original order size |
| `cloid` | string | Client order ID (hex string) |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"openOrders","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required (public data) |
| **Response Size** | ~1-10 KB |

## Limitations

- Returns only open orders
- Cancelled/filled orders not included (see historicalOrders)
- Limited to user's own orders

## Use Cases

- Display user's pending orders
- Monitor order status in real-time
- Implement order management features

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
