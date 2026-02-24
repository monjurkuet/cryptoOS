# Hyperliquid Daily Notional Liquidated by Coin API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/daily_notional_liquidated_by_coin
```

## Description
Returns daily liquidation notional value by coin. Shows total value of positions liquidated per day for each trading pair.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "coin": "RNDR",
      "daily_notional_liquidated": 6772.535123000001
    },
    {
      "time": "2023-06-14T00:00:00",
      "coin": "ARB",
      "daily_notional_liquidated": 969.775709
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `coin` | string | Cryptocurrency ticker (e.g., BTC, ETH, SOL) |
| `daily_notional_liquidated` | number | Total notional value liquidated (USD) |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/daily_notional_liquidated_by_coin" -o data/daily_notional_liquidated_by_coin.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 5.7 MB |
| **Total Records** | ~965 days × ~50+ coins |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **No pagination** - entire liquidation history in single request
- **Daily granularity** - no intraday liquidation data
- **Notional vs Actual Loss**: Value is position size, not user's actual loss
- **Multiple liquidations**: One record per coin per day, all liquidations combined

## 💡 Use Cases

- Identify market stress events (high liquidation days)
- Analyze leverage usage patterns by coin
- Study correlation between price moves and liquidations
- Track market sentiment during volatile periods
- Identify potential support/resistance levels

## 📊 Sample Data

| Date | Coin | Daily Notional Liquidated |
|------|------|---------------------------|
| 2023-06-13 | RNDR | $6,772 |
| 2023-06-14 | ARB | $970 |
| 2023-06-13 | BTC | ~$1.2M |
| 2023-06-13 | ETH | ~$500K |

## Warnings

⚠️ **Not Actual Loss**: This is position size liquidated, not user's PnL loss

⚠️ **High Liquidations = High Risk**: Days with massive liquidations often indicate capitulation

⚠️ **Can Be Zero**: Some coins may have days with no liquidations

## Notes
- Measures liquidation activity, not user losses
- Useful for understanding leverage concentration
- Can predict potential market reversals
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
