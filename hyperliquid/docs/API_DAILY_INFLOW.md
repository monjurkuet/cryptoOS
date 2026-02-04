# Hyperliquid Daily Inflow API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/daily_inflow
```

## Description
Returns daily net inflow metrics showing deposits minus withdrawals per day.

## Response Format
```json
{
  "chart_data": [
    {
      "time": "2023-06-13T00:00:00",
      "inflow": -17420.013762
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `time` | string | ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS) |
| `inflow` | number | Daily net inflow in USD (can be positive or negative) |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/daily_inflow" -o data/daily_inflow.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 59 KB |
| **Total Records** | 965 daily data points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## HTTP Headers
```
Content-Type: binary/octet-stream
Content-Length: 60350
Last-Modified: Tue, 03 Feb 2026 23:43:10 GMT
ETag: "..."
```

## ⚠️ Limitations

- **No filtering parameters** - returns full historical data only
- **No pagination** - entire dataset in single request
- **Daily granularity** - no intraday data available

## 💡 Use Cases

- Identify unusual deposit/withdrawal activity days
- Analyze daily volatility in capital flows
- Detect potential market events (large inflows/outflows)
- Calculate cumulative from daily by summing values

## 📊 Sample Data

| Date | Daily Inflow |
|------|--------------|
| 2023-06-13 | -$17.42K |
| 2023-06-14 | +$12.24K |
| 2023-06-15 | +$47.55K |
| 2023-06-16 | +$85.45K |
| 2023-06-17 | +$11.02K |

## Difference from Cumulative Inflow

| Metric | Daily Inflow | Cumulative Inflow |
|--------|--------------|-------------------|
| Field | `inflow` | `cumulative_inflow` |
| Shows | Daily net flow | Running total |
| Use case | Volatility analysis | Trend analysis |

## Notes
- Positive values = net deposits for that day
- Negative values = net withdrawals for that day
- Useful for detecting unusual activity spikes
- Great for charting daily deposit/withdrawal patterns

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
