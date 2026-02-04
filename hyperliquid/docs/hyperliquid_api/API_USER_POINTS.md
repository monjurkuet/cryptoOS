# Hyperliquid User Points API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "userPoints",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns points earned by a user from Hyperliquid's loyalty program.

## Response Format
```json
{
  "points": "15000.0",
  "breakdown": {
    "trading": "10000.0",
    "staking": "3000.0",
    "referral": "2000.0"
  }
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `points` | string | Total points |
| `breakdown.trading` | string | Points from trading |
| `breakdown.staking` | string | Points from staking |
| `breakdown.referral` | string | Points from referrals |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"userPoints","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## Use Cases

- Display user points balance
- Track point earning activities
- Monitor referral bonuses

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
