# Hyperliquid User Funding API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "userFunding",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2",
  "startTime": 1704067200000
}
```

## Description
Returns funding payments received/paid by a specific user.

## Response Format
```json
[
  {
    "time": 1740009600000,
    "hash": "0x...",
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
| `time` | number | Timestamp (milliseconds) |
| `delta.type` | string | Event type |
| `delta.coin` | string | Coin ticker |
| `delta.usdc` | string | Funding amount (+ received, - paid) |
| `delta.szi` | string | Position size at funding |
| `delta.fundingRate` | string | Funding rate applied |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"userFunding","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2","startTime":1704067200000}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Rate Limit** | Check userRateLimit |

## Use Cases

- Track funding payments
- Calculate funding costs
- Analyze position financing

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
