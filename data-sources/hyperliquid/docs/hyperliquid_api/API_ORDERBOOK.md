# Hyperliquid Orderbook API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "orderbook",
  "coin": "BTC"
}
```

## Description
Returns the orderbook (bids and asks) for a specific perpetual coin.

## Response Format
```json
{
  "coin": "BTC",
  "time": 1770163748294,
  "levels": [
    [
      { "px": "75596.0", "sz": "0.12275", "n": 1 },
      { "px": "75595.0", "sz": "0.12046", "n": 1 }
    ],
    [
      { "px": "75596.0", "sz": "0.12275", "n": 1 }
    ]
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | string | Perpetual coin ticker |
| `time` | number | Snapshot timestamp (milliseconds) |
| `levels[0]` | array | Ask levels (price, size, number of orders) |
| `levels[1]` | array | Bid levels (price, size, number of orders) |
| `px` | string | Price level |
| `sz` | string | Total size at this level |
| `n` | number | Number of orders at this level |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"orderbook","coin":"BTC"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~2-5 KB |

## Limitations

- Returns aggregated orderbook
- Use l2Book for full depth orderbook

## Use Cases

- Display orderbook in trading interface
- Calculate market depth
- Identify support/resistance levels

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
