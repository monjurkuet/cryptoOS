# Hyperliquid Liquidity by Coin API

## Endpoint
```
https://d2v1fiwobg9w6.cloudfront.net/liquidity_by_coin
```

## Description
Returns liquidity metrics by coin including mid price, median liquidity, and slippage estimates for various trade sizes.

## Response Format
```json
{
  "chart_data": {
    "APE": [
      {
        "time": "2023-06-13T00:00:00",
        "mid_price": 2.248545591989537,
        "median_liquidity": 514365.83743,
        "median_slippage_0": 0.00040341599562365715,
        "median_slippage_1000": 0.0004124073249891502,
        "median_slippage_3000": 0.0004981621839674766,
        "median_slippage_10000": 0.000556538517250238,
        "median_slippage_30000": null,
        "median_slippage_100000": null
      }
    ]
  }
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | object | Per-coin liquidity data |
| `time` | string | ISO 8601 timestamp |
| `mid_price` | number | Current mid price of the coin |
| `median_liquidity` | number | Median liquidity available |
| `median_slippage_X` | number | Median slippage for trade size X (USD) |

## Slippage Fields

| Field | Trade Size (USD) |
|-------|-----------------|
| `median_slippage_0` | $0 (base case) |
| `median_slippage_1000` | $1,000 trades |
| `median_slippage_3000` | $3,000 trades |
| `median_slippage_10000` | $10,000 trades |
| `median_slippage_30000` | $30,000 trades |
| `median_slippage_100000` | $100,000 trades |

## Usage
```bash
curl -sL "https://d2v1fiwobg9w6.cloudfront.net/liquidity_by_coin" -o data/liquidity_by_coin.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 47.3 MB (LARGEST dataset) |
| **Total Records** | ~965 days × ~50+ coins × multiple slippage points |
| **Date Range** | Jun 2023 - Present |
| **Content-Type** | binary/octet-stream |
| **Caching** | CloudFront (check Last-Modified header) |
| **Pagination** | ❌ None (full history in one request) |
| **Authentication** | None required |

## ⚠️ Limitations

- **Largest file** - 47 MB, requires good connection
- **No pagination** - entire liquidity history in single request
- **Daily granularity** - no intraday liquidity snapshots
- **Null values** - some slippage fields may be null for illiquid coins

## 💡 Use Cases

- Analyze market depth and liquidity by coin
- Estimate slippage for large trades
- Identify most liquid trading pairs
- Compare liquidity across different coins
- Plan trade execution strategies

## 📊 Sample Data (APE coin)

| Metric | Value |
|--------|-------|
| Mid Price | $2.25 |
| Median Liquidity | 514,365 APE |
| Slippage $0 | 0.04% |
| Slippage $1K | 0.04% |
| Slippage $10K | 0.06% |
| Slippage $30K | N/A |

## Warnings

⚠️ **Large File**: 47 MB download - may timeout on slow connections

⚠️ **Slippage Estimates**: Actual slippage may vary from median

⚠️ **Null Slippage**: High slippage values may be null for illiquid coins

## Notes
- Most comprehensive liquidity dataset
- Useful for understanding market quality
- Slippage increases with trade size
- Updated daily around UTC midnight

## Data Source
CloudFront CDN (d2v1fiwobg9w6.cloudfront.net) - ASXN cached data
