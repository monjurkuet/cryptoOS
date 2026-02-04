# Hyperliquid Largest User Depositors API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors
```

## Description
Returns top 1,000 Hyperliquid users ranked by total deposit amount in USD.

## Response Format
```json
{
  "table_data": [
    {
      "name": "0xa822a9ceb6d6cb5b565bd10098abcfa9cf18d748",
      "value": 22179599135.429718
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | User's Ethereum wallet address (full address) |
| `value` | number | Total deposit amount in USD |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors" -o data/largest_user_depositors.json
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
- Pagination parameters (`?page=2`, `?offset=1000`) **do not work**
- Same data returned regardless of pagination parameters
- **Cannot get more than top 1,000** - this is a hard limit

### Data Considerations
- Some top addresses appear to be contract addresses (starts with 0x2000...)
- Values are raw numbers, not formatted
- Includes both individual users and smart contracts

## 💡 Use Cases

- Identify whale deposit activity
- Study concentration of deposits among top users
- Analyze deposit patterns of top traders
- Track changes in top depositor rankings

## 📊 Sample Data

| Rank | Address | Deposit USD |
|------|---------|-------------|
| 1 | 0xa822...d748 | $22.18B |
| 2 | 0x2000...01b0 | $10.00B |
| 3 | 0x2000...0199 | $9.99B |
| 4 | 0x2000...019e | $9.99B |
| 5 | 0x2000...019f | $9.99B |

## Warnings

⚠️ **Contract Addresses**: Some top "depositors" are smart contract addresses (e.g., 0x2000...), not individual traders. These may be:
- Vault contracts
- Multi-signature wallets
- Smart contract wallets

⚠️ **Duplicate Deposits**: The same user may have multiple addresses

## Notes
- Sorted by total deposit value (descending)
- Values include both historical and current deposits
- Some addresses show suspiciously round numbers (potentialWash trading indicators)
- Updated daily (check `Last-Modified` header)

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
