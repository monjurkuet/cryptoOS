# Hyperliquid Spot Meta API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "spotMeta"
}
```

## Description
Returns metadata about available spot markets.

## Response Format
```json
{
  "universe": [
    {
      "tokens": [1, 0],
      "name": "PURR/USDC",
      "index": 0,
      "isCanonical": true
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `universe[].tokens` | array | Token IDs [base, quote] |
| `universe[].name` | string | Market name |
| `universe[].index` | number | Market index |
| `universe[].isCanonical` | boolean | Whether canonical market |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"spotMeta"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~5 KB |

## Use Cases

- List available spot markets
- Get token IDs for spot trading
- Configure spot trading interface

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
