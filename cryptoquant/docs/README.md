# CryptoQuant API Documentation Index

## Quick Links
- [Main README](../README.md)
- [Market Indicators](API_MARKET_INDICATORS.md)
- [Exchange Flows](API_EXCHANGE_FLOWS.md)
- [Derivatives](API_DERIVATIVES.md)
- [Fund Data](API_FUND_DATA.md)

## Categories

### 📈 Market Indicators
- MVRV Ratio
- Estimated Leverage Ratio
- Spot/Futures Average Order Size
- Spot/Futures Taker CVD
- Spot/Futures Volume Bubble Map
- Spot/Futures Retail Activity
- SOPR, LTH-SOPR, STH-SOPR, aSOPR

### 💰 Exchange Flows
- Exchange Reserve
- Exchange Netflow
- Exchange Inflow/Outflow
- Whale Ratio
- Inflow/Outflow Top30
- Exchange Reserve by Exchange
- Spot/Derivatives Inflow

### 📊 Derivatives
- Funding Rates
- Open Interest
- Long/Short Ratio
- Taker Buy/Sell Volume
- Top Trader Ratio
- Perpetual Funding
- Liquidations
- Options OI
- Basis

### 💎 Fund Data
- Coinbase Premium Index
- Coinbase Premium Gap
- Korea Premium Index
- Stablecoin Supply Ratio
- Market Cap
- Realized Cap
- Average Cap
- Delta Cap
- Thermo Cap
- Price & Volume (USD/KRW)

## Getting Started

1. Get API key from https://cryptoquant.com
2. Set environment variable: `export CRYPTOQUANT_API_KEY="your_key"`
3. Run download scripts from `../scripts/` directory

## Example Usage

```bash
# Download all market indicators
../scripts/download_market_indicators.sh

# Download exchange flows
../scripts/download_exchange_flows.sh

# Download derivatives
../scripts/download_derivatives.sh

# Download fund data
../scripts/download_fund_data.sh
```

## Response Format

All endpoints return GraphQL responses:

```json
{
  "data": {
    "btc": {
      "category": {
        "metric": {
          "value": 1.3573,
          "change24h": -3.85,
          "change7d": -12.4,
          "timestamp": "2026-02-04T12:00:00Z"
        }
      }
    }
  }
}
```
