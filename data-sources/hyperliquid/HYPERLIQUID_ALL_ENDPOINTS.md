# Hyperliquid API Reference - Complete

## Summary

| Source | Endpoints | Total Size | Notes |
|--------|-----------|------------|-------|
| **CloudFront** | 15 | ~76 MB | Market/Trading/User data |
| **Stats Data** | 2 | ~38 MB | Leaderboard + Vaults |
| **TOTAL** | **17** | **~114 MB** | All data |

---

## 📊 All Working Endpoints

### CloudFront (d2v1fiwobg9w6.cloudfront.net)

| # | Endpoint | Size | Description |
|---|----------|------|-------------|
| 1 | `/cumulative_inflow` | 70 KB | Cumulative net inflow |
| 2 | `/daily_inflow` | 60 KB | Daily deposits/withdrawals |
| 3 | `/cumulative_usd_volume` | 64 KB | Cumulative trading volume |
| 4 | `/daily_usd_volume` | 70 KB | Daily trading volume |
| 5 | `/cumulative_trades` | 59 KB | Cumulative number of trades |
| 6 | `/daily_unique_users` | 59 KB | Daily active unique users |
| 7 | `/cumulative_new_users` | 86 KB | New users over time |
| 8 | `/open_interest` | 11.9 MB | Open interest by coin |
| 9 | `/funding_rate` | 11.7 MB | Funding rates by coin |
| 10 | `/liquidity_by_coin` | 47 MB | Liquidity data |
| 11 | `/daily_notional_liquidated_by_coin` | 5.7 MB | Liquidations by coin |
| 12 | `/largest_user_depositors` | 84 KB | Top 1,000 deposits |
| 13 | `/largest_liquidated_notional_by_user` | 80 KB | Top 1,000 liquidations |
| 14 | `/largest_user_trade_count` | 77 KB | Top 1,000 trade counts |
| 15 | `/largest_users_by_usd_volume` | 84 KB | Top 1,000 by volume |

### Stats Data (stats-data.hyperliquid.xyz)

| # | Endpoint | Size | Description |
|---|----------|------|-------------|
| 1 | `/Mainnet/leaderboard` | 25 MB | **30,312** traders with full metrics |
| 2 | `/Mainnet/vaults` | 13 MB | **9,007** vaults with PnL |

---

## 👑 NEW: Vaults Endpoint (9,007 records!)

### Hyperliquid Vaults
```bash
curl -sL "https://stats-data.hyperliquid.xyz/Mainnet/vaults"
```

**Response:**
```json
[
  {
    "summary": {
      "name": "Snipe Trading",
      "vaultAddress": "0x00043d4a2c258892172dc6ce5f62e2e3936ae0dc",
      "leader": "0x9ab020fd91d6909e3d0cbf6c078f8b8163836c06",
      "tvl": "0.000016",
      "isClosed": true
    },
    "pnls": {
      "day": [...],
      "week": [...],
      "month": [...],
      "allTime": [...]
    }
  }
]
```

**Test Results:**
| Metric | Value |
|--------|-------|
| Records | 9,007 vaults |
| Size | 13 MB |
| Single Request | ✅ Yes |

---

## 📈 Data Categories

### Market Metrics
- `cumulative_inflow`, `daily_inflow` - Capital flows
- `cumulative_usd_volume`, `daily_usd_volume` - Volume data
- `cumulative_trades` - Trade count

### User Metrics
- `daily_unique_users` - Daily active users
- `cumulative_new_users` - User growth

### Trading Data
- `open_interest` - By coin, historical (11.9 MB)
- `funding_rate` - By coin, historical (11.7 MB)
- `liquidity_by_coin` - Liquidity (47 MB!)
- `daily_notional_liquidated_by_coin` - Liquidations (5.7 MB)

### Rankings (Top 1,000)
- `largest_user_depositors`
- `largest_liquidated_notional_by_user`
- `largest_user_trade_count`
- `largest_users_by_usd_volume`

### Leaderboard & Vaults
- `Mainnet/leaderboard` - 30K+ traders
- `Mainnet/vaults` - 9K+ vaults

---

## 🚀 Quick Download All

```bash
./download_all_hyperliquid_data.sh
```

Individual downloads:
```bash
./download_leaderboard.sh           # 30K traders
./download_vaults.sh                # 9K vaults
./download_cumulative_inflow.sh
./download_open_interest.sh         # 12 MB
./download_funding_rate.sh           # 12 MB
./download_liquidity_by_coin.sh      # 47 MB (largest!)
# ... etc
```

---

## 📊 Total Data Volume

| Category | Count | Size |
|----------|-------|------|
| Traders | 30,312 | 25 MB |
| Vaults | 9,007 | 13 MB |
| User Rankings | 4,000 | ~325 KB |
| Time Series | 965 days | ~76 MB |
| **TOTAL** | **~43K records** | **~114 MB** |

---

## ✅ All Endpoints Summary

- **No authentication** required
- **CORS enabled** (browser-accessible)
- **No pagination** (full data in one request)
- **Top 1,000 limit** for user rankings
- **Cached data** (check Last-Modified header)
