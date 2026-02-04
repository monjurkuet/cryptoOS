# Hyperliquid Cumulative Inflow API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow
```

## Description
Returns cumulative net inflow data showing total deposits minus withdrawals over time.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "cumulative_inflow": -17420.013762
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `cumulative_inflow` | number | Cumulative net inflow in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow" -o data/cumulative_inflow.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 70 KB |
| **Total Records** | 965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## HTTP Headers
```
Content-Type: binary/octet-stream
Content-Length: 70774
Last-Modified: Tue, 03 Feb 2026 23:43:10 GMT
ETag: "..."
```

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data only
- **No pagination** - entire dataset in single request
- **Daily granularity** - no hourly or minute-level data

## 💡 Use Cases

- Track long-term capital flows into Hyperliquid
- Identify net deposit/withdrawal trends
- Analyze user adoption over time
- Calculate daily net flow by differencing consecutive days

## 📊 Sample Data

| Date | Cumulative Inflow |
|------|-------------------|
| 2023-06-13 | -$17.42K |
| 2023-06-14 | -$5.18K |
| 2023-06-15 | +$42.38K |
| 2023-06-16 | +$127.83K |
| 2023-06-17 | +$138.85K |

## Notes
- Positive values = net deposits exceed withdrawals
- Negative values = net withdrawals exceed deposits
- Data starts from platform launch (June 2023)
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
