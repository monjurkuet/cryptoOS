# Hyperliquid Cumulative Trades API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/cumulative_trades
```

## Description
Returns cumulative number of trades over time since platform launch.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "cumulative": 58325.0
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `cumulative` | number | Cumulative total number of trades |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/cumulative_trades" -o data/cumulative_trades.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 59 KB |
| **Total Records** | ~965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data
- **No pagination** - entire dataset in single request
- **Daily granularity** - no intraday trade counts
- **Cumulative metric** - always increasing

## 💡 Use Cases

- Track platform adoption and usage growth
- Calculate daily trades by differencing consecutive days
- Analyze trading frequency trends
- Compare with volume data for trade size analysis

## 📊 Sample Data

| Date | Cumulative Trades |
|------|------------------|
| 2023-06-13 | 58,325 |
| 2023-06-14 | 72,029 |
| 2023-06-15 | 79,293 |
| 2023-06-16 | ~95,000 |
| 2023-06-17 | ~110,000 |

## Notes
- Cumulative trade count (always increasing)
- Daily trades = cumulative[t] - cumulative[t-1]
- Useful for measuring platform activity
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
