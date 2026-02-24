# Bitcoin Magazine Pro - Complete API Discovery Report

## Executive Summary

**Date**: February 4, 2026  
**Website**: https://www.bitcoinmagazinepro.com  
**API Framework**: Django Plotly Dash  
**Authentication Required**: ✅ **YES** - All real chart data requires Professional Plan subscription

## 🔍 Discovery Results

### Publicly Accessible Endpoints (Metadata Only)
These return component structure but **NOT actual chart data**:
- ✅ `/django_plotly_dash/app/{app}/_dash-layout` - Returns React component layout
- ✅ `/django_plotly_dash/app/{app}/_dash-dependencies` - Returns callback definitions

### Private Endpoints (Require Authentication)
These return **actual chart data** but fail with HTTP 500:
- ❌ `/django_plotly_dash/app/{app}/_dash-update-component` - Returns chart figure data

### Public Widget (Free)
- ✅ Fear & Greed Index widget - JavaScript embed (not raw data API)

## 📊 Complete API Endpoint List

### Market Cycle Charts (11 endpoints)

| Chart | App Name | Layout URL | Data URL |
|-------|----------|------------|----------|
| Bitcoin Investor Tool | `market_cycle_ma` | ✅ Public | ❌ Auth Required |
| 200 Week MA Heatmap | `200wma_heatmap` | ✅ Public | ❌ Auth Required |
| Stock-to-Flow | `stock_flow` | ✅ Public | ❌ Auth Required |
| Fear & Greed Index | `fear_and_greed` | ✅ Public | ❌ Auth Required |
| Pi Cycle Top | `pi_cycle_top_indicator` | ✅ Public | ❌ Auth Required |
| Golden Ratio | `golden_ratio` | ✅ Public | ❌ Auth Required |
| Profitable Days | `profitable_day` | ✅ Public | ❌ Auth Required |
| Rainbow Chart | `rainbow` | ✅ Public | ❌ Auth Required |
| Pi Cycle Prediction | `pi_cycle_top_e` | ✅ Public | ❌ Auth Required |
| Power Law | `power_law` | ✅ Public | ❌ Auth Required |

### Onchain Indicators (25+ endpoints)

| Chart | App Name |
|-------|----------|
| MVRV Z-Score | `mvrv_z` |
| RHODL Ratio | `rhodl_ratio` |
| NUPL | `unreali` |
| Reserve Risk | `re` |
| Realized Price | `realized_price` |
| VDD Multiple | `vdd_multiple` |
| CVDD | `cvdd` |
| Top Cap | `top_cap` |
| Delta Top | `delta_top` |
| Balanced Price | `balanced_price` |
| Terminal Price | `terminal_price` |
| LTH Realized | `realized_price_lth` |
| STH Realized | `realized_price_` |

### Onchain Movement (11+ endpoints)

| Chart | App Name |
|-------|----------|
| HODL Waves | `hodl_wave` |
| 5Y HODL Wave | `hodl_wave_5y` |
| 10Y HODL Wave | `hodl_wave_10y` |
| Realized Cap HODL | `rcap_hodl_wave` |
| Whale Shadows | `whale_watching` |
| Coin Days Destroyed | `bdd` |
| Supply Adjusted CDD | `bdd_` |
| LTH Supply | `lth_` |
| Circulating Supply | `circulating_` |

### Address Balance Charts (20+ endpoints)

| Chart | App Name |
|-------|----------|
| Active Addresses | `active_addre` |
| Min 0.01 BTC | `min_001_count` |
| Min 0.1 BTC | `min_01_count` |
| Min 1 BTC | `min_1_count` |
| Min 10 BTC | `min_10_count` |
| Min 100 BTC | `min_100_count` |
| Min 1,000 BTC | `min_1000_count` |
| Min 10,000 BTC | `min_10000_count` |
| Non-zero | `min_0_count` |
| New Addresses | `new_addre` |

### Mining Charts (12+ endpoints)

| Chart | App Name |
|-------|----------|
| Puell Multiple | `puell_multiple` |
| Hash Ribbons | `ha` |
| Miner Difficulty | `miner_difficulty` |
| Miner Revenue Total | `miner_revenue_total` |
| Miner Revenue Block | `miner_revenue_block_reward` |
| Miner Revenue Fees | `miner_revenue_fee` |

### Lightning Network (2 endpoints)

| Chart | App Name |
|-------|----------|
| Lightning Capacity | `lightning_capacity` |
| Lightning Nodes | `lightning_node` |

### Derivatives (2 endpoints)

| Chart | App Name |
|-------|----------|
| Open Interest | `open_intere` |
| Funding Rates | `funding_rate` |

## 🔧 API Usage

### Get Chart Layout (Public)
```bash
curl "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-layout"
```

**Response** (React component structure, not data):
```json
{
  "props": {
    "children": [
      {
        "props": {
          "id": "chart",
          "config": {"displayModeBar": false}
        }
      }
    ]
  }
}
```

### Get Dependencies (Public)
```bash
curl "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-dependencies"
```

**Response** (Callback definitions):
```json
[
  {
    "inputs": [
      {"id": "url", "property": "pathname"},
      {"id": "display", "property": "children"}
    ],
    "output": "chart.figure"
  }
]
```

### Get Chart Data (Requires Auth)
```bash
curl -X POST "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-update-component" \
  -H "Content-Type: application/json" \
  -d '{
    "output": "chart.figure",
    "outputs": [{"id": "chart", "property": "figure"}],
    "inputs": [
      {"id": "url", "property": "pathname", "value": "/charts/puell-multiple/"},
      {"id": "display", "property": "children"}
    ],
    "state": []
  }'
```

**Response** (Without auth):
```html
<!doctype html>
<html>
<head><title>Server Error (500)</title></head>
<body><h1>Server Error (500)</h1></body>
</html>
```

## 📦 Repository Structure
```
bitcoinmagazinepro/
├── README.md                    # This comprehensive report
├── .gitignore
├── docs/
│   ├── API_INDEX.md            # Quick reference index
│   ├── API_FEAR_AND_GREED.md   # Fear & Greed endpoint docs
│   ├── API_MVRV_ZSCORE.md      # MVRV Z-Score docs
│   └── API_Puell_Multiple.md   # Puell Multiple docs
├── scripts/
│   ├── download_all.sh         # Endpoint documentation script
│   ├── download_chart.sh        # Individual chart lookup
│   └── test_endpoints.sh        # Endpoint tester
└── data/                       # (Empty - no free data available)
```

## 🎁 FREE Alternative: Fear & Greed Widget

While there's no free raw data API, a public widget is available:

**URL**: `https://www.bitcoinmagazinepro.com/widget/fear-and-greed/`

**Embed Code**:
```html
<div id="fear_and_greed" style="width:100%">
  <a href="https://www.bitcoinmagazinepro.com/charts/bitcoin-fear-and-greed-index/" target="_blank">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <div id="header"></div>
    <div id="plotly_app"></div>
  </a>
  <script type="text/javascript" src="https://www.bitcoinmagazinepro.com/widget/fear-and-greed/"></script>
</div>
```

## 💰 Subscription Required for Data Access

To access real chart data, you need:
1. **Professional Plan** subscription
2. **API Key** from https://www.bitcoinmagazinepro.com/api/
3. **Authenticated session** with proper cookies

## 🔗 Free Bitcoin Data Alternatives

For developers seeking free Bitcoin on-chain data:

| Source | URL | Best For |
|--------|-----|----------|
| CoinGecko | https://www.coingecko.com/ | Price, market data |
| CryptoCompare | https://www.cryptocompare.com/ | Historical data |
| Blockchain.info | https://www.blockchain.com/ | Raw blockchain |
| Glassnode Studio | https://studio.glassnode.com/ | On-chain metrics (limited free) |
| CoinMetrics | https://coinmetrics.io/ | Network data |

## 📝 Conclusion

**Bitcoin Magazine Pro does NOT offer free public APIs.** All chart data requires:
- Professional Plan subscription
- API authentication
- Valid session credentials

The website's Django Plotly Dash architecture provides:
- ✅ Public component layouts (for embedding reference)
- ❌ Private data endpoints (require auth)

**Recommendation**: Subscribe to Professional Plan for full API access, or use free alternatives listed above.
