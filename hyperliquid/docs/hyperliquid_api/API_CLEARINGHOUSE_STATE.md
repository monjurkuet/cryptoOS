# Hyperliquid Clearinghouse State API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "clearinghouseState",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns complete clearinghouse state for a user including account value, positions, and margin information.

## Response Format
```json
{
  "marginSummary": {
    "accountValue": "1513034.031499",
    "totalNtlPos": "2487281.4142900002",
    "totalRawUsd": "3593185.340909",
    "totalMarginUsed": "214001.86356"
  },
  "crossMarginSummary": {
    "accountValue": "1513034.031499",
    "totalNtlPos": "2487281.4142900002",
    "totalRawUsd": "3593185.340909",
    "totalMarginUsed": "214001.86356"
  },
  "crossMaintenanceMarginUsed": "58380.115202",
  "withdrawable": "566166.912793",
  "assetPositions": [
    {
      "type": "oneWay",
      "position": {
        "coin": "BTC",
        "szi": "0.96468",
        "leverage": { "type": "cross", "value": 20 },
        "entryPx": "75590.4",
        "positionValue": "72934.6314",
        "unrealizedPnl": "14.01093",
        "returnOnEquity": "0.0038427896",
        "liquidationPx": null,
        "marginUsed": "3646.73157",
        "maxLeverage": 40,
        "cumFunding": {
          "allTime": "154777.434473",
          "sinceOpen": "0.0",
          "sinceChange": "0.0"
        }
      }
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `marginSummary.accountValue` | string | Total account value in USD |
| `marginSummary.totalNtlPos` | string | Total notional positions value |
| `marginSummary.totalRawUsd` | string | Raw USD value including leverage |
| `marginSummary.totalMarginUsed` | string | Total margin currently used |
| `crossMaintenanceMarginUsed` | string | Maintenance margin required |
| `withdrawable` | string | Withdrawable amount in USD |
| `assetPositions[].position.coin` | string | Perpetual coin ticker (BTC, ETH, etc.) |
| `assetPositions[].position.szi` | string | Position size (signed) |
| `assetPositions[].position.leverage.value` | number | Leverage multiplier |
| `assetPositions[].position.entryPx` | string | Average entry price |
| `assetPositions[].position.positionValue` | string | Position value in USD |
| `assetPositions[].position.unrealizedPnl` | string | Unrealized PnL |
| `assetPositions[].position.returnOnEquity` | string | Return on equity (decimal) |
| `assetPositions[].position.liquidationPx` | string \| null | Liquidation price |
| `assetPositions[].position.marginUsed` | string | Margin used for position |
| `assetPositions[].position.maxLeverage` | number | Maximum allowed leverage |
| `assetPositions[].position.cumFunding.allTime` | string | Cumulative funding paid/received |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"clearinghouseState","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required (public data) |
| **Rate Limit** | Check userRateLimit endpoint |
| **Response Size** | ~5-50 KB (depends on positions) |

## Limitations

- **No pagination** - returns all positions in single request
- **Real-time data** - may be slightly delayed
- **Position values are strings** - requires parsing for calculations

## Use Cases

- Display user portfolio overview
- Calculate account health and liquidation risk
- Track position PnL in real-time
- Monitor margin usage

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
