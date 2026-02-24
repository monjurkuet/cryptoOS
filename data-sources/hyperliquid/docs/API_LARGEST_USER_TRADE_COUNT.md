# Hyperliquid Largest User Trade Count API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count
```

## Description
Returns top 1,000 users ranked by total number of trades executed on Hyperliquid.

## Response Format
```json
{
  "table_data": [
    {
      "name": "0x644f7170fae9d4d173d9217f03b7a77e22ed98f1",
      "value": 675745729.0
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User's Ethereum wallet address (full address) |
| `value` | number | Total number of trades executed |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count" -o data/largest_user_trade_count.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 76 KB |
| **Total Records** | 1,000 users |
| **Pagination** | ❌ None (fixed top 1000) |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Authentication** | None required |

## ⚠️ Limitations

### Hard Limit: Top 1,000 Only
- Only returns **exactly 1,000 records**
- Pagination parameters **do not work**
- Cannot get trade counts beyond top 1,000 users
- **This is a hard limit** - cannot query more data

### Data Considerations
- High trade counts may indicate:
  - Scalping strategies
  - High-frequency trading
  - Bot activity
  - Sample size bias (more trades = more data collected)

## 💡 Use Cases

- Identify most active traders on platform
- Study trading frequency vs profitability correlation
- Analyze market making activity
- Identify potential bot/script traders

## 📊 Sample Data

| Rank | Address | Trade Count |
|------|---------|-------------|
| 1 | 0x644f...98f1 | 675.75M |
| 2 | 0x7717...bd7e | 578.89M |
| 3 | 0x98da...6de1 | 509.16M |
| 4 | 0x4edd...b7fc | 467.33M |
| 5 | 0xdcac...9ce2 | 441.93M |

## Warnings

⚠️ **High-Frequency Trading**: Top traders with 500M+ trades likely use automated trading systems

⚠️ **Volume vs Trades**: High trade count doesn't mean high volume (could be small positions)

## Notes
- Sorted by trade count (descending)
- Trade counts are cumulative since account creation
- Useful for identifying power users
- Updated daily (check `Last-Modified` header)

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
