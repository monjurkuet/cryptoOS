# Hyperliquid Spot Clearinghouse State API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "spotClearinghouseState",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns spot (non-perpetual) clearinghouse state for a user.

## Response Format
```json
{
  "balances": [
    {
      "coin": "USDC",
      "token": 0,
      "total": "0.99788573",
      "hold": "0.0",
      "entryNtl": "0.0"
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `balances[].coin` | string | Token symbol |
| `balances[].token` | number | Token ID |
| `balances[].total` | string | Total balance |
| `balances[].hold` | string | Held balance (in orders) |
| `balances[].entryNtl` | string | Entry notional value |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"spotClearinghouseState","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~1-5 KB |

## Use Cases

- Display spot balances
- Calculate total portfolio value
- Monitor available balance for trading

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
