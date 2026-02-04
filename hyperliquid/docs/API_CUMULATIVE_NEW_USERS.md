# Hyperliquid Cumulative New Users API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/cumulative_new_users
```

## Description
Returns cumulative count of new users and daily new user signups over time.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "daily_new_users": 101,
      "cumulative_new_users": 101
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `daily_new_users` | number | New users that day |
| `cumulative_new_users` | number | Running total of new users |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/cumulative_new_users" -o data/cumulative_new_users.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 86 KB |
| **Total Records** | ~965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data
- **No pagination** - entire dataset in single request
- **Daily granularity** - no hourly signup data
- **"New user" definition** may vary (first deposit, first trade)

## 💡 Use Cases

- Track user acquisition over time
- Analyze growth rate of platform
- Identify successful user acquisition campaigns
- Calculate user growth percentage
- Compare new user trends across periods

## 📊 Sample Data

| Date | Daily New Users | Cumulative Users |
|------|-----------------|------------------|
| 2023-06-13 | 101 | 101 |
| 2023-06-14 | 186 | 287 |
| 2023-06-15 | 135 | 422 |
| 2023-06-16 | ~200 | ~622 |
| 2023-06-17 | ~180 | ~802 |

## Notes
- Contains both daily and cumulative metrics
- Useful for growth analysis
- Can identify spikes in user acquisition
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
