# Hyperliquid Funding History API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "fundingHistory",
  "coin": "BTC"
}
```

## Description
Returns historical funding rates for a specific perpetual coin.

## Response Format
```json
[
  {
    "time": 1740009600000,
    "hash": "0x0000000000000000000000000000000000000000000000000000000000000000",
    "delta": {
      "type": "funding",
      "coin": "HYPE",
      "usdc": "-0.007411",
      "szi": "1.0",
      "fundingRate": "0.0000200887",
      "nSamples": 15
    }
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | number | Funding timestamp (milliseconds) |
| `delta.type` | string | Event type (funding) |
| `delta.coin` | string | Coin ticker |
| `delta.usdc` | string | Funding payment in USDC |
| `delta.szi` | string | Position size |
| `delta.fundingRate` | string | Funding rate |
| `delta.nSamples` | number | Number of samples |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"fundingHistory","coin":"BTC"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~50-200 KB |

## Use Cases

- Analyze funding rate trends
- Calculate funding costs
- Monitor market sentiment

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
