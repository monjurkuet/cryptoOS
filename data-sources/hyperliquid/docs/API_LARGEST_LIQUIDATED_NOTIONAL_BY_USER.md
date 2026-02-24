# Hyperliquid Largest Liquidated Notional by User API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user
```

## Description
Returns top 1,000 users ranked by total liquidation amount (notional value) in USD.

## Response Format
```json
{
  "table_data": [
    {
      "name": "0xf3f496c9486be5924a93d67e98298733bb47057c",
      "value": 331975245.91053
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User's Ethereum wallet address (full address) |
| `value` | number | Total liquidated position value in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user" -o data/largest_liquidated_notional_by_user.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 80 KB |
| **Total Records** | 1,000 users |
| **Pagination** | ❌ None (fixed top 1000) |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Authentication** | None required |

## ⚠️ Limitations

### Hard Limit: Top 1,000 Only
- Only returns **exactly 1,000 records**
- Pagination parameters **do not work**
- Cannot get liquidation history beyond top 1,000 users
- **This is a hard limit** - cannot query more data

### Data Considerations
- "Notional" refers to position size, not actual loss amount
- High liquidation values may indicate over-leveraged traders
- Some users may have been liquidated multiple times

## 💡 Use Cases

- Identify most aggressive/leverage-heavy traders
- Study liquidation patterns and market stress
- Analyze risk management behaviors
- Identify traders who recovered after liquidations

## 📊 Sample Data

| Rank | Address | Liquidated USD |
|------|---------|----------------|
| 1 | 0xf3f4...057c | $331.98M |
| 2 | 0xb317...83ae | $222.66M |
| 3 | 0x0a07...1801 | $93.01M |
| 4 | 0x7905...3f21 | $83.65M |
| 5 | 0xd5ff...1070 | $61.20M |

## Warnings

⚠️ **Not Notional vs Loss**: This is position size liquidated, not actual PnL loss. A user liquidated for $1M may have only lost a fraction of that.

⚠️ **Multiple Liquidations**: A user can appear multiple times if liquidated on different occasions

## Notes
- Sorted by total liquidation notional (descending)
- Useful for understanding leverage concentration
- May correlate with volatile market periods
- Updated daily (check `Last-Modified` header)

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
