# Hyperliquid Trades API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "trades",
  "coin": "BTC"
}
```

## Description
Returns recent public trades for a specific perpetual coin.

## Response Format
```json
[
  {
    "coin": "BTC",
    "px": "75590.0",
    "sz": "0.01",
    "side": "A",
    "time": 1770163764000,
    "hash": "0x...",
    "tid": 123456789
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | string | Perpetual coin ticker |
| `px` | string | Trade price |
| `sz` | string | Trade size |
| `side` | string | "A" (Ask/Sell) or "B" (Bid/Buy) |
| `time` | number | Trade timestamp (milliseconds) |
| `hash` | string | Transaction hash |
| `tid` | number | Trade ID |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"trades","coin":"BTC"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~5-20 KB |

## Use Cases

- Display recent trades
- Track trade history
- Analyze market activity

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
