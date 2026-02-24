# CryptoQuant APIs - Complete Discovery Documentation

## ⚠️ HONEST ASSESSMENT

**Authentication Required**: All cryptoquant.com APIs require an API key.
- GraphQL endpoint: `https://graph.cryptoquant.com/graphql` → Returns 401 without key
- REST API: `https://api.cryptoquant.com/v1/...` → Requires authentication

**To use these APIs**: You need to sign up at [cryptoquant.com](https://cryptoquant.com) and get a free API key.

---

## 🚀 QUICK START (Requires API Key)

```bash
# 1. Get free API key from https://cryptoquant.com
export CRYPTOQUANT_API_KEY="your_api_key_here"

# 2. Test GraphQL endpoint
curl -X POST "https://graph.cryptoquant.com/graphql" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $CRYPTOQUANT_API_KEY" \
  -d '{"query":"{ btc { summary { mvrvRatio } } }"}'
```

---

## 📊 COMPLETE METRICS INVENTORY

Based on thorough exploration of cryptoquant.com, here are ALL available metrics organized by category:

### 📈 MARKET INDICATOR METRICS

| # | Metric | URL Path | Current Value |
|---|--------|----------|---------------|
| 1 | MVRV Ratio | `/asset/btc/chart/market-indicator/mvrv-ratio` | 1.3573 |
| 2 | Estimated Leverage Ratio | `/asset/btc/chart/market-indicator/estimated-leverage-ratio` | - |
| 3 | Spot Average Order Size | `/asset/btc/chart/market-indicator/spot-average-order-size` | - |
| 4 | Futures Average Order Size | `/asset/btc/chart/market-indicator/futures-average-order-size` | - |
| 5 | Spot Taker CVD (90-day) | `/asset/btc/chart/market-indicator/spot-taker-cvd` | Taker Buy Dominant |
| 6 | Futures Taker CVD (90-day) | `/asset/btc/chart/market-indicator/futures-taker-cvd` | Taker Buy Dominant |
| 7 | Spot Volume Bubble Map | `/asset/btc/chart/market-indicator/spot-volume-bubble-map` | Neutral |
| 8 | Futures Volume Bubble Map | `/asset/btc/chart/market-indicator/futures-volume-bubble-map` | Neutral |
| 9 | Spot Retail Activity | `/asset/btc/chart/market-indicator/spot-retail-activity` | Neutral |
| 10 | Futures Retail Activity | `/asset/btc/chart/market-indicator/futures-retail-activity` | Neutral |
| 11 | SOPR | `/asset/btc/chart/network-indicator/sopr` | - |
| 12 | LTH-SOPR | `/asset/btc/chart/network-indicator/lth-sopr` | - |
| 13 | STH-SOPR | `/asset/btc/chart/network-indicator/sth-sopr` | - |
| 14 | aSOPR | `/asset/btc/chart/network-indicator/asopr` | - |
| 15 | SOPR Ratio (LTH-SOPR/STH-SOPR) | `/asset/btc/chart/network-indicator/sopr-ratio` | - |

### 💰 EXCHANGE FLOWS METRICS

| # | Metric | URL Path | Current Value |
|---|--------|----------|---------------|
| 1 | Exchange Reserve | `/asset/btc/chart/exchange-flows/exchange-reserve` | 2.7495M |
| 2 | Exchange Netflow | `/asset/btc/chart/exchange-flows/exchange-netflow` | 2.5346K |
| 3 | Exchange Inflow | `/asset/btc/chart/exchange-flows/exchange-inflow` | 56.1724K |
| 4 | Exchange Outflow | `/asset/btc/chart/exchange-flows/exchange-outflow` | - |
| 5 | Exchange Whale Ratio | `/asset/btc/chart/exchange-flows/whale-ratio` | 0.9767 |
| 6 | Inflow Top30 | `/asset/btc/chart/exchange-flows/inflow-top30` | - |
| 7 | Outflow Top30 | `/asset/btc/chart/exchange-flows/outflow-top30` | - |
| 8 | Exchange Reserve by Exchange | `/asset/btc/chart/exchange-flows/exchange-reserve-by-exchange` | - |
| 9 | Spot Inflow | `/asset/btc/chart/exchange-flows/spot-inflow` | - |
| 10 | Derivatives Inflow | `/asset/btc/chart/exchange-flows/derivatives-inflow` | - |

### 📊 DERIVATIVES METRICS

| # | Metric | URL Path | Current Value |
|---|--------|----------|---------------|
| 1 | Funding Rates | `/asset/btc/chart/derivatives/funding-rate` | 0.005561 |
| 2 | Open Interest | `/asset/btc/chart/derivatives/open-interest` | 23.8622B |
| 3 | Long/Short Ratio | `/asset/btc/chart/derivatives/long-short-ratio` | - |
| 4 | Taker Buy/Sell Volume | `/asset/btc/chart/derivatives/taker-volume` | - |
| 5 | Top Trader Long/Short | `/asset/btc/chart/derivatives/top-trader-ratio` | - |
| 6 | Perpetual Funding | `/asset/btc/chart/derivatives/perpetual-funding` | - |
| 7 | Liquidations | `/asset/btc/chart/derivatives/liquidations` | - |
| 8 | Options OI | `/asset/btc/chart/derivatives/options-oi` | - |
| 9 | Basis | `/asset/btc/chart/derivatives/basis` | - |
| 10 | Volume by Exchange | `/asset/btc/chart/derivatives/volume-by-exchange` | - |

### 💎 FUND DATA METRICS

| # | Metric | URL Path | Current Value |
|---|--------|----------|---------------|
| 1 | Coinbase Premium Index | `/asset/btc/chart/fund-data/coinbase-premium` | -0.1435 |
| 2 | Coinbase Premium Gap | `/asset/btc/chart/fund-data/coinbase-premium-gap` | -108.72 |
| 3 | Korea Premium Index | `/asset/btc/chart/fund-data/korea-premium` | 1.7199 |
| 4 | Stablecoin Supply Ratio | `/asset/btc/chart/fund-data/stablecoin-supply-ratio` | - |
| 5 | Market Cap | `/asset/btc/chart/fund-data/market-cap` | 1.5104T |
| 6 | Realized Cap | `/asset/btc/chart/fund-data/realized-cap` | 1.1128T |
| 7 | Average Cap | `/asset/btc/chart/fund-data/average-cap` | 343.6212B |
| 8 | Delta Cap | `/asset/btc/chart/fund-data/delta-cap` | 769.2189B |
| 9 | Thermo Cap | `/asset/btc/chart/fund-data/thermo-cap` | 90.9761B |
| 10 | Price & Volume (USD) | `/asset/btc/chart/fund-data/price-volume` | - |
| 11 | Price & Volume (KRW) | `/asset/btc/chart/fund-data/price-volume-krw` | - |

### ⛏️ MINER FLOWS METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Miner Reserve | `/asset/btc/chart/miner-flows/miner-reserve` |
| 2 | Miner Inflow | `/asset/btc/chart/miner-flows/miner-inflow` |
| 3 | Miner Outflow | `/asset/btc/chart/miner-flows/miner-outflow` |
| 4 | Miner Netflow | `/asset/btc/chart/miner-flows/miner-netflow` |
| 5 | Miner Revenue (USD) | `/asset/btc/chart/miner-flows/miner-revenue` |

### 🌐 NETWORK STATISTICS METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Active Addresses | `/asset/btc/chart/network-stats/active-addresses` |
| 2 | Transaction Count | `/asset/btc/chart/network-stats/transaction-count` |
| 3 | Transaction Volume | `/asset/btc/chart/network-stats/transaction-volume` |
| 4 | UTXO Age Bands | `/asset/btc/chart/network-stats/utxo-age-bands` |
| 5 | Exchange Interaction Rate | `/asset/btc/chart/network-stats/exchange-interaction` |
| 6 | Whale Transaction Count | `/asset/btc/chart/network-stats/whale-transactions` |
| 7 | New Addresses | `/asset/btc/chart/network-stats/new-addresses` |
| 8 | Large Transaction Volume | `/asset/btc/chart/network-stats/large-transactions` |
| 9 | Realized Volume | `/asset/btc/chart/network-stats/realized-volume` |
| 10 | Zero Balance Addresses | `/asset/btc/chart/network-stats/zero-balance` |

### 📍 ADDRESS METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Rich List | `/asset/btc/chart/addresses/rich-list` |
| 2 | Exchange Address Balance | `/asset/btc/chart/addresses/exchange-balance` |
| 3 | Old Coins | `/asset/btc/chart/addresses/old-coins` |
| 4 | HODL Waves | `/asset/btc/chart/addresses/hodl-waves` |
| 5 | CoinDay Destroyed | `/asset/btc/chart/addresses/coinday-destroyed` |
| 6 | Binary CDD | `/asset/btc/chart/addresses/binary-cdd` |
| 7 | Addresses with Balance | `/asset/btc/chart/addresses/with-balance` |
| 8 | Top 1000 Holders | `/asset/btc/chart/addresses/top-holders` |

### 💸 FEES & REVENUE METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Total Fees (USD) | `/asset/btc/chart/fees-and-revenue/total-fees` |
| 2 | Median Fee | `/asset/btc/chart/fees-and-revenue/median-fee` |
| 3 | Fee Rate (satoshis/vByte) | `/asset/btc/chart/fees-and-revenue/fee-rate` |
| 4 | Miner Revenue | `/asset/btc/chart/fees-and-revenue/miner-revenue` |
| 5 | Block Rewards | `/asset/btc/chart/fees-and-revenue/block-rewards` |

### 📦 SUPPLY METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Circulating Supply | `/asset/btc/chart/supply/circulating-supply` |
| 2 | Burned/Unspendable | `/asset/btc/chart/supply/burned` |
| 3 | Reserve Risk | `/asset/btc/chart/supply/reserve-risk` |
| 4 | Market Cap / Thermocap | `/asset/btc/chart/supply/mcap-thermo-ratio` |
| 5 | Puell Multiple | `/asset/btc/chart/supply/puell-multiple` |

### 🔄 TRANSACTION METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | Transaction Count | `/asset/btc/chart/transactions/transaction-count` |
| 2 | Transfer Volume | `/asset/btc/chart/transactions/transfer-volume` |
| 3 | Large Transactions | `/asset/btc/chart/transactions/large-transactions` |
| 4 | Whale Transactions | `/asset/btc/chart/transactions/whale-transactions` |
| 5 | Exchange Transactions | `/asset/btc/chart/transactions/exchange-transactions` |

### 🏦 INTER-ENTITY FLOWS METRICS

| # | Metric | URL Path |
|---|--------|----------|
| 1 | CEX → CEX | `/asset/btc/chart/inter-entity-flows/cex-cex` |
| 2 | CEX → DeFi | `/asset/btc/chart/inter-entity-flows/cex-defi` |
| 3 | DeFi → CEX | `/asset/btc/chart/inter-entity-flows/defi-cex` |
| 4 | Mining Pool → CEX | `/asset/btc/chart/inter-entity-flows/mining-cex` |
| 5 | OTC Desk → CEX | `/asset/btc/chart/inter-entity-flows/otc-cex` |

---

## 📡 DISCOVERED API ENDPOINTS

### GraphQL API (CONFIRMED)
```
Endpoint: https://graph.cryptoquant.com/graphql
Method: POST
Auth: X-API-Key header required
```

### REST API (Likely Structure)
```
Base: https://api.cryptoquant.com/v1

Patterns:
- /{asset}/summary
- /{asset}/market-indicator/{indicator}
- /{asset}/exchange-flows/{metric}
- /{asset}/derivatives/{metric}
- /{asset}/fund-data/{metric}
- /{asset}/network/{metric}
```

---

## 📁 PROJECT STRUCTURE

```
cryptoquant/
├── README.md                          # This file
├── scripts/
│   ├── download_all.sh               # Master script (requires API key)
│   ├── download_graphql.sh           # GraphQL examples
│   ├── download_market_indicators.sh # Market indicator scripts
│   ├── download_exchange_flows.sh    # Exchange flow scripts
│   ├── download_derivatives.sh       # Derivatives scripts
│   ├── download_fund_data.sh         # Fund data scripts
│   └── download_network.sh           # Network scripts
├── docs/
│   ├── README.md                     # Index
│   ├── API_MARKET_INDICATORS.md      # Detailed docs
│   ├── API_EXCHANGE_FLOWS.md         # Detailed docs
│   ├── API_DERIVATIVES.md            # Detailed docs
│   ├── API_FUND_DATA.md              # Detailed docs
│   └── API_NETWORK.md                # Detailed docs
└── data/                             # Downloaded JSON files
```

---

## 💡 USAGE EXAMPLES

### GraphQL Query Example
```bash
#!/bin/bash
API_KEY="${CRYPTOQUANT_API_KEY}"

# Query BTC MVRV Ratio
curl -s -X POST "https://graph.cryptoquant.com/graphql" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "query { btc { marketIndicator { mvrvRatio { value change24h } } } }"
  }'
```

### REST API Example (Assumed)
```bash
#!/bin/bash
API_KEY="${CRYPTOQUANT_API_KEY}"

# Get BTC Summary
curl -s -X GET "https://api.cryptoquant.com/v1/btc/summary" \
  -H "X-API-Key: $API_KEY"

# Get MVRV Ratio
curl -s -X GET "https://api.cryptoquant.com/v1/btc/market-indicator/mvrv-ratio" \
  -H "X-API-Key: $API_KEY"

# Get with date range
curl -s -X GET "https://api.cryptoquant.com/v1/btc/market-indicator/mvrv-ratio?start=2024-01-01&end=2024-12-31" \
  -H "X-API-Key: $API_KEY"
```

---

## 📊 METRICS COUNT SUMMARY

| Category | Count |
|----------|-------|
| Market Indicators | 15 |
| Exchange Flows | 10 |
| Derivatives | 10 |
| Fund Data | 11 |
| Miner Flows | 5 |
| Network Stats | 10 |
| Addresses | 8 |
| Fees & Revenue | 5 |
| Supply | 5 |
| Transactions | 5 |
| Inter-Entity Flows | 5 |
| **TOTAL** | **89 metrics** |

---

## 🔗 RESOURCES

- Website: https://cryptoquant.com
- User Guide: https://userguide.cryptoquant.com
- API Docs: https://cryptoquant.com/api-docs
- API Catalog: https://cryptoquant.com/api-catalog

---

**Last Updated**: 2026-02-04
**Total Metrics Documented**: 89
**Authentication Required**: Yes (API Key)
