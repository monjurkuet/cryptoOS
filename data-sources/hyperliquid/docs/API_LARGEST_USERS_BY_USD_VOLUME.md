# Hyperliquid Largest Users by USD Volume API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume
```

## Description
Returns top 1,000 users ranked by total trading volume in USD.

## Response Format
```json
{
  "table_data": [
    {
      "name": "0x023a3d058020fb76cca98f01b3c48c8938a22355",
      "value": 221658360596.36298
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User's Ethereum wallet address (full address) |
| `value` | number | Total trading volume in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume" -o data/largest_users_by_usd_volume.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 84 KB |
| **Total Records** | 1,000 users |
| **Pagination** | ❌ None (fixed top 1000) |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Authentication** | None required |

## ⚠️ Limitations

### Hard Limit: Top 1,000 Only
- Only returns **exactly 1,000 records**
- Pagination parameters **do not work**
- Cannot get volume data beyond top 1,000 users
- **This is a hard limit** - cannot query more data

### Data Considerations
- Volume includes both opening and closing trades
- Some volume may be from position hedging
- Round numbers may indicate automated trading

## 💡 Use Cases

- Identify whale traders by volume
- Study volume concentration among top traders
- Analyze trading patterns of high-volume users
- Identify potential market makers

## 📊 Sample Data

| Rank | Address | Volume USD |
|------|---------|------------|
| 1 | 0x023a...2355 | $221.66B |
| 2 | 0xecb6...2b00 | $218.64B |
| 3 | 0x162c...8185 | $164.36B |
| 4 | 0xc6ac...884 | $138.66B |
| 5 | 0x7b7f...ee2 | $136.02B |

## Alternative Data Source

For **complete volume data** for all 30,000+ traders:
- Use the [Leaderboard API](API_LEADERBOARD.md) which includes volume in `windowPerformances`
- Each trader has volume for day/week/month/allTime timeframes
- More comprehensive but requires additional processing

## Warnings

⚠️ **Volume Concentration**: Top 10 traders likely account for significant portion of total volume

⚠️ **Includes Opening + Closing**: Volume counts both sides of each trade

## Notes
- Sorted by total volume (descending)
- Volume is cumulative since account creation
- Useful for understanding market liquidity providers
- Updated daily (check `Last-Modified` header)

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
