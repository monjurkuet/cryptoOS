# Hyperliquid API Reference

## All Endpoints Overview

| # | Endpoint | Records | Size | Pagination | All-in-One |
|---|----------|---------|------|-------------|------------|
| 1 | https://stats-data.hyperliquid.xyz/Mainnet/leaderboard | 30,312 | 25 MB | ❌ None | ✅ Yes |
| 2 | https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors | 1,000 | 84 KB | ❌ Fixed | ✅ Yes |
| 3 | https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user | 1,000 | 80 KB | ❌ Fixed | ✅ Yes |
| 4 | https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count | 1,000 | 76 KB | ❌ Fixed | ✅ Yes |
| 5 | https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume | 1,000 | 84 KB | ❌ Fixed | ✅ Yes |
| 6 | https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow | 965 | 70 KB | ❌ None | ✅ Yes |
| 7 | https://d2v1fiwobg9w6.cloudfront.net/daily_inflow | 965 | 59 KB | ❌ None | ✅ Yes |

## Quick Start

### Download All Data
```bash
./download_all_hyperliquid_apis.sh
```

### Download Individual Files
```bash
./download_leaderboard.sh              # 30K traders with full metrics
./download_largest_user_depositors.sh   # Top 1,000 deposits
./download_largest_liquidated_notional_by_user.sh  # Top 1,000 liquidations
./download_largest_user_trade_count.sh   # Top 1,000 trade counts
./download_largest_users_by_usd_volume.sh  # Top 1,000 by volume
./download_cumulative_inflow.sh         # Historical cumulative flow
./download_daily_inflow.sh              # Historical daily flow
```

## Key Findings

### ✅ Good News
- **All endpoints work** with simple curl requests
- **No authentication required**
- **CORS enabled** (can be used from browser)
- **All data in single request** - no pagination needed
- **Complete datasets** - each endpoint returns full available data

### ⚠️ Limitations
- **Top 1,000 only** for user ranking endpoints (cannot get more)
- **No pagination** support on CloudFront endpoints
- **Fixed limits** - cannot query beyond top 1000 traders/positions
- **Cache-based** - may not have latest real-time data

## Pagination Status

| Endpoint | Pagination | Notes |
|----------|------------|-------|
| leaderboard | ❌ None | Returns ALL 30K+ traders in one request |
| largest_user_depositors | ❌ Fixed | Only returns top 1000, cannot paginate |
| largest_liquidated_notional_by_user | ❌ Fixed | Only returns top 1000, cannot paginate |
| largest_user_trade_count | ❌ Fixed | Only returns top 1000, cannot paginate |
| largest_users_by_usd_volume | ❌ Fixed | Only returns top 1000, cannot paginate |
| cumulative_inflow | ❌ None | Full history (965 days) in one request |
| daily_inflow | ❌ None | Full history (965 days) in one request |

## Suggestions for Getting More Data

If you need more than top 1000:
1. **Leaderboard** - Already has all 30K traders, use this for comprehensive data
2. **User Rankings** - Hard limits, consider:
   - Querying blockchain directly
   - Using Dune Analytics
   - Contacting ASXN for bulk data access

## Data Sources
- **stats-data.hyperliquid.xyz**: Hyperliquid official stats
- **d2v1fiwobg9w6.cloudfront.net**: ASXN cached data (CloudFront CDN)

## API Documentation
- [Leaderboard](API_LEADERBOARD.md) - 30K+ traders with full metrics
- [Largest User Depositors](API_LARGEST_USER_DEPOSITORS.md) - Top 1,000 deposits
- [Largest Liquidated Notional](API_LARGEST_LIQUIDATED_NOTIONAL_BY_USER.md) - Top 1,000 liquidations
- [Largest Trade Count](API_LARGEST_USER_TRADE_COUNT.md) - Top 1,000 trade counts
- [Largest Users by USD Volume](API_LARGEST_USERS_BY_USD_VOLUME.md) - Top 1,000 by volume
- [Cumulative Inflow](API_CUMULATIVE_INFLOW.md) - Historical cumulative flow
- [Daily Inflow](API_DAILY_INFLOW.md) - Historical daily flow

## Update Frequency
| Endpoint | Update Frequency |
|----------|------------------|
| leaderboard | Daily |
| user rankings | Daily |
| inflow data | Daily |
