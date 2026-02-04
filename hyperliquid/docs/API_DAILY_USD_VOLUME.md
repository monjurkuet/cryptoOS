# Hyperliquid Daily USD Volume API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/daily_usd_volume
```

## Description
Returns daily trading volume in USD showing day-over-day trading activity.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "daily_usd_volume": 5077264.726494786
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `daily_usd_volume` | number | Daily trading volume in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/daily_usd_volume" -o data/daily_usd_volume.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 70 KB |
| **Total Records** | ~965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data
- **No pagination** - entire dataset in single request
- **Daily granularity** - no intraday or hourly data
- **Includes all trades** - both opening and closing trades counted

## 💡 Use Cases

- Analyze daily market activity patterns
- Identify high-volume trading days
- Detect unusual trading activity
- Calculate volatility in trading volume
- Day-of-week analysis

## 📊 Sample Data

| Date | Daily Volume |
|------|--------------|
| 2023-06-13 | $5.08M |
| 2023-06-14 | $3.46M |
| 2023-06-15 | $8.48M |
| 2023-06-16 | ~$10M |
| 2023-06-17 | ~$11M |

## Notes
- Shows actual daily trading volume
- Useful for identifying market events
- Can correlate with price movements
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
