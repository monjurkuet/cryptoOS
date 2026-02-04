# Hyperliquid Leaderboard API

## Endpoint
```
https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
```

## Description
Returns top 30,312+ Hyperliquid traders with full performance metrics across multiple timeframes (day, week, month, allTime).

## Response Format
```json
{
  "leaderboardRows": [
    {
      "ethAddress": "0x162cc7c861ebd0c06b3d72319201150482518185",
      "accountValue": "48857952.3308470026",
      "windowPerformances": [
        ["day", { "pnl": "644054.375913", "roi": "0.0133582723", "vlm": "3250555746.66" }],
        ["week", { "pnl": "3528804.427511", "roi": "0.0729632296", "vlm": "22918292160.97" }],
        ["month", { "pnl": "876456.769935", "roi": "0.0158501266", "vlm": "48037528566.37" }],
        ["allTime", { "pnl": "30223465.310847", "roi": "0.4895956489", "vlm": "608739069893.13" }]
      ],
      "prize": 0,
      "displayName": "ABC"
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `ethAddress` | string | Trader's Ethereum wallet address (lowercase, no 0x prefix) |
| `accountValue` | string | Current account value in USD (precise decimal) |
| `displayName` | string \| null | Custom display name (optional, can be null) |
| `prize` | number | Competition prize amount earned |
| `windowPerformances[].pnl` | string | Profit/Loss in USD for timeframe |
| `windowPerformances[].roi` | string | Return on Investment (decimal, e.g., 0.01 = 1%) |
| `windowPerformances[].vlm` | string | Trading volume in USD for timeframe |

## Timeframes

| Timeframe | Description |
|-----------|-------------|
| `day` | Last 24 hours performance |
| `week` | Last 7 days performance |
| `month` | Last 30 days performance |
| `allTime` | Lifetime performance since account creation |

## Usage
```bash
curl -sL "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard" -o data/leaderboard.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 25 MB |
| **Total Records** | 30,312 traders |
| **Pagination** | ❌ None (all data in single request) |
| **Download Time** | ~3-5 seconds (larger file) |
| **Content-Type** | application/json |
| **Authentication** | None required |

## ⚠️ Limitations

- **No filtering parameters** - returns all traders
- **No pagination** - entire leaderboard in single request
- **Large response size** - 25 MB, may timeout on slow connections
- **Account values are strings** - requires parsing to float for calculations

## 💡 Use Cases

- Analyze top trader performance
- Identify successful trading strategies
- Track trader rankings over time
- Calculate aggregate statistics across traders
- Study correlation between volume and PnL

## 📊 Sample Data

| Rank | Address | Account Value | Day PnL | Day ROI | Day Volume |
|------|---------|---------------|---------|---------|------------|
| 1 | 0x162c...8185 | $48.86M | +$644K | +1.34% | $3.25B |
| 2 | 0x87f9...e2cf | $85.89M | +$1.44M | +1.68% | $5.12B |
| 3 | 0x2000...01b0 | $10.00B | +$0 | +0% | $0 |

## Notes
- Traders are **not sorted by account value** - appears to be sorted by allTime volume
- Display names are user-set and may contain special characters
- Account values include all assets (spot + perp positions)
- ROI is calculated as (PnL / Initial Capital)
- Updated daily (check `Last-Modified` header)

## Data Source
Hyperliquid official stats endpoint (stats-data.hyperliquid.xyz)
