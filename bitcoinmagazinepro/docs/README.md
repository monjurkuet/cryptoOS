# Bitcoin Magazine Pro API Documentation

## ⚠️ IMPORTANT: API Access Requires Authentication

All Bitcoin Magazine Pro API endpoints require authentication and a Professional Plan subscription. **No public APIs are available.**

## Documentation Index

### API Overview
- [API Discovery Report](../README.md) - Complete analysis of all attempted API endpoints

## Quick Start (For Subscribers)

### Authentication

**Header Method (Recommended):**
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  "https://api.bitcoinmagazinepro.com/metrics"
```

**URL Parameter Method:**
```bash
curl "https://api.bitcoinmagazinepro.com/metrics?key=YOUR_API_KEY"
```

### Available Endpoints

1. **List All Metrics**
   - Endpoint: `GET https://api.bitcoinmagazinepro.com/metrics`
   - Parameters: `hourly=1` (optional, returns only hourly metrics)

2. **Get Specific Metric**
   - Endpoint: `GET https://api.bitcoinmagazinepro.com/metrics/{metric_name}`

3. **Get Metric with Date Range**
   - Endpoint: `GET https://api.bitcoinmagazinepro.com/metrics/{metric_name}?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`

4. **Get Hourly Data**
   - Endpoint: `GET https://api.bitcoinmagazinepro.com/metrics/{metric_name}?hourly=1`

## Metric Categories

### Market Cycle Indicators
- Bitcoin Investor Tool: 2-Year MA Multiplier
- 200 Week Moving Average Heatmap
- Stock-to-Flow Model
- Fear And Greed Index
- Pi Cycle Top Indicator
- Golden Ratio Multiplier
- Bitcoin Profitable Days
- Bitcoin Rainbow Price Chart Indicator
- Pi Cycle Top & Bottom Indicator
- Pi Cycle Top Prediction
- Power Law

### Onchain Indicators
- MVRV Z-Score
- RHODL Ratio
- Net Unrealized Profit/Loss (NUPL)
- Reserve Risk
- AASI (Active Address Sentiment Indicator)
- Advanced NVT Signal
- Realized Price
- Value Days Destroyed (VDD) Multiple
- CVDD
- Top Cap, Delta Top, Balanced Price, Terminal Price
- Long-Term Holder Realized Price
- Short-Term Holder Realized Price
- Percent Addresses in Profit/Loss
- SOPR (Spent Output Profit Ratio)
- Short/Long Term Holder MVRV
- Everything Indicator

### Onchain Movement
- HODL Waves (1y, 5y, 10y)
- Realized Cap HODL Waves
- Whale Shadows (Revived Supply)
- Coin Days Destroyed
- Supply Adjusted Coin Days Destroyed
- Circulating Supply
- Long/Short Term Holder Supply

### Address Balance Charts
- Active Addresses
- Addresses with Balance > 0.01 BTC, 0.1 BTC, 1 BTC, 10 BTC, 100 BTC, 1000 BTC, 10000 BTC
- Addresses with Balance > $1, $10, $100, $1k, $10k, $100k, $1m
- Non-zero Addresses
- New Addresses

### Mining Metrics
- Puell Multiple
- Hash Ribbons Indicator
- Miner Difficulty
- Miner Revenue (Total, Block Rewards, Fees, Fees %)
- Block Height
- Blocks Mined
- Hashprice & Hashprice Volatility

### Lightning Network
- Lightning Capacity
- Lightning Nodes

### Derivatives
- Bitcoin Funding Rates (fr-average)
- Bitcoin Open Interest

### Macro Suite
- High Yield Credit vs BTC
- Manufacturing PMI vs BTC
- US M1/M2 Money vs BTC (various timeframes)
- Global M2 vs BTC
- Fed Balance Sheet vs BTC
- Fed Funds Target Range
- US Interest Payments vs BTC
- US Debt/GDP Ratio vs BTC
- Financial Stress Index vs BTC
- Bull Market Comparison

## Data Format

All API responses return CSV-formatted data.

### Example Response Structure
```csv
date,value
2010-01-01,0.01
2010-01-02,0.02
...
```

### Date Range Parameters
- `from_date`: Start date in YYYY-MM-DD format (optional)
- `to_date`: End date in YYYY-MM-DD format (optional)
- Either or both can be provided

## Hourly Data

The following metrics support hourly data with the `hourly=1` parameter:
- fr-average, fr-binance, fr-bitfinex, fr-bitmex, fr-bybit, fr-okx
- golden-ratio, 200wma-heatmap, investor-tool, pi-cycle-top, profitable-days

## Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 401 | Authentication credentials not provided |
| 403 | Invalid authentication credentials |
| 404 | Endpoint or metric not found |

## Rate Limits

Specific rate limits are not documented but are enforced based on subscription tier.

## Subscription Information

- **Professional Plan Required**: Contact https://www.bitcoinmagazinepro.com/subscribe/
- **Support**: https://www.bitcoinmagazinepro.com/contact-us/

## Alternative Free Data Sources

If you cannot access the Professional API, consider:
- CoinGecko API (free tier available)
- CryptoCompare API (free tier available)
- Glassnode Studio (free tier available)
- Blockchain.info (free endpoints available)

## Last Updated
February 4, 2026
