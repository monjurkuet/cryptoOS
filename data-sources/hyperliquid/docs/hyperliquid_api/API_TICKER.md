# Hyperliquid Ticker API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "ticker",
  "coin": "BTC"
}
```

## Description
Returns 24-hour ticker information for a specific perpetual coin.

## Response Format
```json
{
  "time": 1770163764451,
  "coin": "BTC",
  "px": "75590.0",
  "lsz": "0.0001",
  "csxl": "12",
  "vl": 15600000,
  "volume": "15600000",
  "minPx": "73000.0",
  "maxPx": "76000.0",
  "oltm": 1770163764000,
  "strikePxs": [],
  "postOnly": false,
  "params": []
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | number | Current timestamp |
| `coin` | string | Perpetual coin ticker |
| `px` | string | Current mark price |
| `lsz` | string | Last trade size |
| `csxl` | string | Number of trades in 24h |
| `vl` | number | 24h volume (in coins) |
| `volume` | string | 24h volume in USD |
| `minPx` | string | 24h low price |
| `maxPx` | string | 24h high price |
| `oltm` | number | Open interest timestamp |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"ticker","coin":"BTC"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~1 KB |

## Use Cases

- Display 24h price statistics
- Track price changes
- Monitor trading volume

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
