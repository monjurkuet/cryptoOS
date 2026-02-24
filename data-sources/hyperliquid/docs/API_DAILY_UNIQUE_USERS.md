# Hyperliquid Daily Unique Users API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/daily_unique_users
```

## Description
Returns daily count of unique active users who traded on Hyperliquid each day.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "daily_unique_users": 101
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `daily_unique_users` | number | Number of unique active users that day |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/daily_unique_users" -o data/daily_unique_users.json
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
- **Daily granularity** - no hourly user activity data
- **Definition of "unique user"** may vary (wallet address, trading activity)

## 💡 Use Cases

- Track Daily Active Users (DAU) growth
- Analyze user engagement trends
- Identify seasonal patterns in trading activity
- Calculate user retention metrics
- Compare DAU across different periods

## 📊 Sample Data

| Date | Daily Unique Users |
|------|-------------------|
| 2023-06-13 | 101 |
| 2023-06-14 | 251 |
| 2023-06-15 | 267 |
| 2023-06-16 | ~350 |
| 2023-06-17 | ~400 |

## Notes
- Measures Daily Active Users (DAU)
- Key metric for platform engagement
- Can correlate with marketing events or market volatility
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
