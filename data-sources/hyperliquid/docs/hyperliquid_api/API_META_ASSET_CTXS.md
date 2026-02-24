# Hyperliquid Meta and Asset Contexts API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "metaAndAssetCtxs"
}
```

## Description
Returns metadata about all available perpetual markets and their contexts.

## Response Format
```json
[
  {
    "universe": [
      {
        "szDecimals": 5,
        "name": "BTC",
        "maxLeverage": 40,
        "marginTableId": 56
      },
      {
        "szDecimals": 4,
        "name": "ETH",
        "maxLeverage": 25,
        "marginTableId": 55
      }
    ]
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `universe[].szDecimals` | number | Size decimal places |
| `universe[].name` | string | Coin ticker |
| `universe[].maxLeverage` | number | Maximum allowed leverage |
| `universe[].marginTableId` | number | Margin table reference |
| `universe[].isDelisted` | boolean | Whether coin is delisted |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"metaAndAssetCtxs"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~10 KB |

## Use Cases

- Get list of available markets
- Display market specifications
- Configure trading parameters

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
