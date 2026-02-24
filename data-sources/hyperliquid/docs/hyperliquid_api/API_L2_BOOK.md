# Hyperliquid L2 Book API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "l2Book",
  "coin": "BTC"
}
```

## Description
Returns full depth orderbook (Level 2) with all price levels for a specific perpetual coin.

## Response Format
```json
{
  "coin": "BTC",
  "time": 1770163748294,
  "levels": [
    [
      { "px": "75596.0", "sz": "0.12275", "n": 1 },
      { "px": "75595.0", "sz": "0.12046", "n": 1 }
      // ... more ask levels
    ],
    [
      { "px": "75590.0", "sz": "0.1225", "n": 2 },
      { "px": "75589.0", "sz": "0.15262", "n": 4 }
      // ... more bid levels
    ]
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | string | Perpetual coin ticker |
| `time` | number | Snapshot timestamp (milliseconds) |
| `levels[0]` | array | Full ask levels |
| `levels[1]` | array | Full bid levels |
| `px` | string | Price |
| `sz` | string | Total size at this level |
| `n` | number | Number of orders at this level |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"l2Book","coin":"BTC"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~10-50 KB (full depth) |

## Limitations

- Returns full depth (more data than orderbook)
- Higher rate limits apply

## Use Cases

- Full market depth analysis
- Implement professional trading interface
- Calculate true liquidity

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
