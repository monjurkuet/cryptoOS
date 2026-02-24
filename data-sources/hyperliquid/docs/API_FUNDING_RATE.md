# Hyperliquid Funding Rate API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/funding_rate
```

## Description
Returns historical funding rates by coin. Funding rates are periodic payments between long and short position holders.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "coin": "CRV",
      "sum_funding": -1.1218588475502809
    },
    {
      "time": "2023-06-13T00:00:00",
      "coin": "RNDR",
      "sum_funding": -1.9900615112679396
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `coin` | string | Cryptocurrency ticker (e.g., BTC, ETH, SOL) |
| `sum_funding` | number | Cumulative funding rate (likely period sum) |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/funding_rate" -o data/funding_rate.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 11.7 MB |
| **Total Records** | ~965 days × ~50+ coins |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **Large file size** - 11.7 MB, may be slow to download
- **No pagination** - entire funding history in single request
- **Daily granularity** - no hourly funding data
- **Sum field unclear** - exact calculation method not documented

## 💡 Use Cases

- Analyze market sentiment (positive funding = longs pay shorts)
- Identify overleveraged markets
- Study funding rate arbitrage opportunities
- Track funding rate trends by coin
- Calculate average funding for position sizing

## 📊 Sample Data

| Date | Coin | Sum Funding |
|------|------|-------------|
| 2023-06-13 | CRV | -1.12 |
| 2023-06-13 | RNDR | -1.99 |
| 2023-06-13 | BTC | ~0.01 |

## Funding Rate Interpretation

| Value | Meaning |
|-------|---------|
| Positive | Long positions pay short positions (longs bullish) |
| Negative | Short positions pay long positions (shorts bullish) |
| High magnitude | High leverage imbalance |

## Warnings

⚠️ **Negative Funding = Shorts Dominant**: Market may be overleveraged on shorts

⚠️ **Extreme Values**: Very high funding rates often precede reversals

## Notes
- Funding rates typically expressed as percentage per 8 hours
- This API returns cumulative sum, may need conversion
- Useful for identifying trend strength
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
