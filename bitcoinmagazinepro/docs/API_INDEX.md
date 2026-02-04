# Bitcoin Magazine Pro API Documentation Index

## ⚠️ Authentication Required

All Bitcoin Magazine Pro API endpoints require authentication and are only accessible to Professional Plan subscribers.

## API Architecture

### Base URL
```
https://www.bitcoinmagazinepro.com/django_plotly_dash/app/{app_name}/
```

### Endpoints Available

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/django_plotly_dash/app/{app}/_dash-layout` | Get chart layout |
| GET | `/django_plotly_dash/app/{app}/_dash-dependencies` | Get callbacks |
| POST | `/django_plotly_dash/app/{app}/_dash-update-component` | Update chart |

## Chart Categories

### Market Cycle (11 charts)
- Bitcoin Investor Tool: `/market_cycle_ma/`
- 200 Week MA Heatmap: `/200wma_heatmap/`
- Stock-to-Flow: `/stock_flow/`
- Fear & Greed Index: `/fear_and_greed/`
- Pi Cycle Top: `/pi_cycle_top_indicator/`
- Golden Ratio: `/golden_ratio/`
- Profitable Days: `/profitable_day/`
- Rainbow Chart: `/rainbow/`
- Pi Cycle Top Prediction: `/pi_cycle_top_e/`
- Power Law: `/power_law/`

### Onchain Indicators (25+ charts)
- MVRV Z-Score: `/mvrv_z/`
- RHODL Ratio: `/rhodl_ratio/`
- NUPL: `/unreali/`
- Reserve Risk: `/re/`
- Realized Price: `/realized_price/`
- VDD Multiple: `/vdd_multiple/`
- CVDD: `/cvdd/`
- Top Cap: `/top_cap/`
- Delta Top: `/delta_top/`
- Balanced Price: `/balanced_price/`
- Terminal Price: `/terminal_price/`
- LTH Realized: `/realized_price_lth/`
- STH Realized: `/realized_price_/`

### Onchain Movement (11+ charts)
- HODL Waves: `/hodl_wave/`
- 5Y HODL Wave: `/hodl_wave_5y/`
- 10Y HODL Wave: `/hodl_wave_10y/`
- Realized Cap HODL: `/rcap_hodl_wave/`
- Whale Shadows: `/whale_watching/`
- Coin Days Destroyed: `/bdd/`
- Supply Adjusted CDD: `/bdd_/`
- LTH Supply: `/lth_/`
- Circulating Supply: `/circulating_/`

### Address Balance (20+ charts)
- Active Addresses: `/active_addre/`
- Min 0.01 BTC: `/min_001_count/`
- Min 0.1 BTC: `/min_01_count/`
- Min 1 BTC: `/min_1_count/`
- Min 10 BTC: `/min_10_count/`
- Min 100 BTC: `/min_100_count/`
- Min 1000 BTC: `/min_1000_count/`
- Min 10000 BTC: `/min_10000_count/`
- Non-zero: `/min_0_count/`
- New Addresses: `/new_addre/`

### Mining (12+ charts)
- Puell Multiple: `/puell_multiple/`
- Hash Ribbons: `/ha/`
- Miner Difficulty: `/miner_difficulty/`
- Miner Revenue Total: `/miner_revenue_total/`
- Miner Revenue Block: `/miner_revenue_block_reward/`
- Miner Revenue Fees: `/miner_revenue_fee/`

### Lightning Network (2 charts)
- Lightning Capacity: `/lightning_capacity/`
- Lightning Nodes: `/lightning_node/`

### Derivatives (2 charts)
- Open Interest: `/open_intere/`
- Funding Rates: `/funding_rate/`

## Usage with Authentication

These APIs require authenticated sessions. Use proper cookies/auth headers.

## Alternative: Free Widget

Fear & Greed widget is publicly available:
```
https://www.bitcoinmagazinepro.com/widget/fear-and-greed/
```

## For Free Data Sources

See README.md for alternative free Bitcoin APIs.
