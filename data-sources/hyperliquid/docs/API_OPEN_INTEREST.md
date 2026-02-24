# Hyperliquid Open Interest API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/open_interest
```

## Description
Returns historical open interest data by coin. Open interest represents total value of open positions for each trading pair.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "coin": "ATOM",
      "open_interest": 7176.773738377629
    },
    {
      "time": "2023-06-13T00:00:00",
      "coin": "CFX",
      "open_interest": 421.83447278660657
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `coin` | string | Cryptocurrency ticker (e.g., BTC, ETH, SOL) |
| `open_interest` | number | Open interest value for that coin |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/open_interest" -o data/open_interest.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 11.9 MB |
| **Total Records** | ~965 days × ~50+ coins |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **Large file size** - 11.9 MB, may be slow to download
- **No pagination** - entire OI history in single request
- **Daily granularity** - no hourly OI data
- **Multiple records per day** - one record per coin per day

## 💡 Use Cases

- Analyze market sentiment (high OI = more leverage/risk)
- Identify potential liquidations during price moves
- Track leverage usage trends by coin
- Calculate OI-to-volume ratios
- Study market structure changes

## 📊 Sample Data

| Date | Coin | Open Interest |
|------|------|---------------|
| 2023-06-13 | BTC | ~$250M |
| 2023-06-13 | ETH | ~$50M |
| 2023-06-13 | SOL | ~$25M |

## Warnings

⚠️ **High Open Interest = High Risk**: Coins with very high OI may experience larger liquidations during price moves

⚠️ **OI vs Volume**: High OI doesn't necessarily mean high liquidity

## Notes
- Open interest varies by coin and market conditions
- Can spike during volatile periods
- Useful for understanding leverage concentration
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
