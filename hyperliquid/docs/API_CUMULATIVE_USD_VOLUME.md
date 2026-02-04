# Hyperliquid Cumulative USD Volume API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/cumulative_usd_volume
```

## Description
Returns cumulative trading volume in USD over time since platform launch.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "cumulative": 5077264.726494786
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `cumulative` | number | Cumulative trading volume in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/cumulative_usd_volume" -o data/cumulative_usd_volume.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 64 KB |
| **Total Records** | ~965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## HTTP Headers
```
Content-Type: binary/octet-stream
Content-Length: 64008
Last-Modified: Tue, 03 Feb 2026 23:43:10 GMT
ETag: "52acb13d53d4acb57dc3e7c08b80105e"
```

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data
- **No pagination** - entire dataset in single request
- **Daily granularity** - no intraday volume data
- **Cumulative metric** - always increasing, cannot get daily directly

## 💡 Use Cases

- Track platform growth over time
- Analyze total trading activity trends
- Calculate daily volume by differencing consecutive days
- Compare trading activity across different periods

## 📊 Sample Data

| Date | Cumulative Volume |
|------|-------------------|
| 2023-06-13 | $5.08M |
| 2023-06-14 | $8.53M |
| 2023-06-15 | $17.01M |
| 2023-06-16 | ~$27M |
| 2023-06-17 | ~$38M |

## Notes
- Cumulative metric (always increasing)
- Useful for long-term trend analysis
- Daily volume = cumulative[t] - cumulative[t-1]
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
