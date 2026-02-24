# Verified Bitcoin On-Chain APIs

## Summary of API Testing (February 2026)

This document contains only APIs that were **actually tested and verified working**. All connectors have been implemented and are available in the market-scraper framework.

---

## Implementation Status

| Connector | Status | File Location |
|-----------|--------|---------------|
| BlockchainInfo | ✅ Implemented | `src/market_scraper/connectors/blockchain_info/` |
| FearGreed | ✅ Implemented | `src/market_scraper/connectors/fear_greed/` |
| CoinMetrics | ✅ Implemented | `src/market_scraper/connectors/coin_metrics/` |
| CBBI | ✅ Implemented | `src/market_scraper/connectors/cbbi/` |
| Bitview | ✅ Implemented | `src/market_scraper/connectors/bitview/` |
| ExchangeFlow | ✅ Implemented | `src/market_scraper/connectors/exchange_flow/` |

---

## 1. Blockchain.info Charts API ⭐⭐⭐⭐⭐ (FULLY WORKING)

**Base URL:** `https://api.blockchain.info/charts/{chart_name}`

**Parameters:**
- `timespan`: e.g., "30days", "1year", "all"
- `format`: "json" (recommended) or "csv"
- `cors=true`: Enable CORS

**Rate Limits:** None documented

**Verified Working Endpoints:**

| Chart Name | Description | Unit | Response Format |
|------------|-------------|------|-----------------|
| `hash-rate` | Network hash rate | TH/s | Daily values |
| `difficulty` | Mining difficulty | Difficulty | Daily values |
| `n-transactions` | Confirmed transactions per day | Count | Daily |
| `n-unique-addresses` | Unique addresses used | Count | Daily |
| `market-price` | BTC price | USD | Daily |
| `market-cap` | Market capitalization | USD | Daily |
| `total-bitcoins` | Circulating supply | BTC | Daily |
| `mempool-count` | Unconfirmed transactions | Count | Minute-level |
| `estimated-transaction-volume-usd` | Transaction volume | USD | Daily |

**Example Response:**
```json
{
  "status": "ok",
  "name": "Hash Rate",
  "unit": "Hash Rate TH/s",
  "period": "day",
  "description": "The estimated number of tera hashes per second...",
  "values": [
    {"x": 1771286400, "y": 1032365847.4243727},
    ...
  ]
}
```

**Usage Example:**
```bash
curl "https://api.blockchain.info/charts/hash-rate?timespan=30days&format=json"
```

---

## 2. Blockchain.info Simple Query API ⭐⭐⭐⭐⭐ (FULLY WORKING)

**Base URL:** `https://blockchain.info/q/{query}`

**Rate Limits:** 1 request per 10 seconds (documented)

**Verified Working Endpoints:**

| Endpoint | Description | Response Type |
|----------|-------------|---------------|
| `/hashrate` | Current hash rate (GH/s) | Number |
| `/getdifficulty` | Current difficulty | Number |
| `/getblockcount` | Current block height | Number |
| `/totalbc` | Total BTC in circulation | Number (satoshis) |
| `/24hrprice` | 24-hour average price | Number (USD) |
| `/marketcap` | Market capitalization | Number (USD) |
| `/24hrtransactioncount` | Transactions in 24h | Number |
| `/24hrbtcsent` | BTC sent in 24h | Number (satoshis) |
| `/unconfirmedcount` | Mempool transactions | Number |

**Example Usage:**
```bash
curl "https://blockchain.info/q/hashrate"
# Returns: 813379152516 (GH/s)
```

---

## 3. Alternative.me Fear & Greed Index ⭐⭐⭐⭐⭐ (FULLY WORKING)

**Base URL:** `https://api.alternative.me/fng/`

**Parameters:**
- `limit`: Number of results (0 = all available)
- `format`: "json" or "csv"
- `date_format`: "us", "cn", "kr", "world" (defaults to unix timestamp)

**Rate Limits:** None documented (commercial use requires attribution)

**Example Response:**
```json
{
  "name": "Fear and Greed Index",
  "data": [
    {
      "value": "8",
      "value_classification": "Extreme Fear",
      "timestamp": "1771372800",
      "time_until_update": "24706"
    }
  ],
  "metadata": {"error": null}
}
```

**Usage Example:**
```bash
curl "https://api.alternative.me/fng/?limit=10"
```

---

## 4. Coin Metrics Community API ⭐⭐⭐⭐ (LIMITED FREE TIER)

**Base URL:** `https://community-api.coinmetrics.io/v4`

**Authentication:** None required for community endpoints

**Verified Free Metrics:**

| Metric ID | Description | Available |
|-----------|-------------|-----------|
| `PriceUSD` | BTC price in USD | ✅ Yes |
| `CapMrktCurUSD` | Market capitalization | ✅ Yes |
| `AdrActCnt` | Active addresses count | ✅ Yes |
| `TxCnt` | Transaction count | ✅ Yes |
| `BlkCnt` | Block count | ✅ Yes |
| `SplyCur` | Current supply | ✅ Yes |

**Metrics NOT Available in Free Tier:**

| Metric ID | Reason |
|-----------|--------|
| `CapMVRVZ` | Requires paid subscription |
| `CapRealUSD` | Requires paid subscription |
| `DiffMean` | Requires paid subscription |
| `BlkSizeByte` | Requires paid subscription |
| `FeeMedUSD` | Requires paid subscription |
| `TxTfrValAdjUSD` | Requires paid subscription |

**Example Response:**
```json
{
  "data": [{
    "asset": "btc",
    "time": "2026-02-17T00:00:00.000000000Z",
    "AdrActCnt": "595445",
    "BlkCnt": "165",
    "CapMrktCurUSD": "1348806897572.94",
    "PriceUSD": "67471.05",
    "SplyCur": "19990898.03",
    "TxCnt": "661420"
  }]
}
```

**Usage Example:**
```bash
curl "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD,AdrActCnt,TxCnt&start_time=2026-02-17&end_time=2026-02-18"
```

---

## 5. APIs That Require Authentication/Payment

| API | Status | Notes |
|-----|--------|-------|
| BGeometrics | Requires API key | Free tier: 8 req/hour |
| ResearchBitcoin.net | Requires token | Free token required |
| CryptoQuant | Requires API key | Paid tiers from $19/mo |
| Glassnode | Requires API key | Paid tiers from $39/mo |

---

## Implementation Priority

Based on verification results, implement in this order:

### Phase 1: Free APIs (Immediate Implementation)
1. **Blockchain.info Charts Connector** - Best free source for network metrics
2. **Fear & Greed Connector** - Sentiment data
3. **Coin Metrics Community Connector** - Price and basic metrics

### Phase 2: Auth Required (If Needed)
4. **BGeometrics Connector** - Exchange flows, MVRV, SOPR (requires API key)
5. **ResearchBitcoin Connector** - 350+ metrics (requires free token)

---

## Data Mapping for Implementation

### Network Activity Metrics
| Metric | Best Source | Endpoint |
|--------|-------------|----------|
| Hash Rate | Blockchain.info | `/charts/hash-rate` |
| Difficulty | Blockchain.info | `/charts/difficulty` |
| Transaction Count | Blockchain.info | `/charts/n-transactions` |
| Active Addresses | Coin Metrics | `AdrActCnt` |
| Unique Addresses | Blockchain.info | `/charts/n-unique-addresses` |

### Price & Market Metrics
| Metric | Best Source | Endpoint |
|--------|-------------|----------|
| BTC Price | Coin Metrics | `PriceUSD` |
| Market Cap | Coin Metrics | `CapMrktCurUSD` |
| Supply | Coin Metrics | `SplyCur` |

### Sentiment Metrics
| Metric | Best Source | Endpoint |
|--------|-------------|----------|
| Fear & Greed Index | Alternative.me | `/fng/` |

### Advanced Metrics (CBBI already covers)
| Metric | Source | Notes |
|--------|--------|-------|
| MVRV Z-Score | CBBI | Already implemented |
| Puell Multiple | CBBI | Already implemented |
| NUPL/RUPL | CBBI | Already implemented |
| Reserve Risk | CBBI | Already implemented |

---

---

## Implementation Status

### ✅ Implemented Connectors

| Connector | File Location | Status |
|-----------|---------------|--------|
| BlockchainInfoConnector | `src/market_scraper/connectors/blockchain_info/` | ✅ Implemented |
| FearGreedConnector | `src/market_scraper/connectors/fear_greed/` | ✅ Implemented |
| CoinMetricsConnector | `src/market_scraper/connectors/coin_metrics/` | ✅ Implemented |

### Usage Example

```python
import asyncio
from market_scraper.connectors.blockchain_info import BlockchainInfoConnector, BlockchainInfoConfig
from market_scraper.connectors.fear_greed import FearGreedConnector, FearGreedConfig
from market_scraper.connectors.coin_metrics import CoinMetricsConnector, CoinMetricsConfig

async def main():
    # Blockchain.info - Network metrics
    bc_config = BlockchainInfoConfig(name="blockchain_info")
    bc = BlockchainInfoConnector(bc_config)
    await bc.connect()
    metrics = await bc.get_current_metrics()
    print(f"Block Height: {metrics.payload['block_height']}")
    print(f"Hash Rate: {metrics.payload['hash_rate_ghs']} GH/s")
    await bc.disconnect()

    # Fear & Greed - Sentiment
    fg_config = FearGreedConfig(name="fear_greed")
    fg = FearGreedConnector(fg_config)
    await fg.connect()
    index = await fg.get_current_index()
    print(f"Fear & Greed: {index.payload['value']} ({index.payload['classification']})")
    await fg.disconnect()

    # Coin Metrics - Price and basic metrics
    cm_config = CoinMetricsConfig(name="coin_metrics")
    cm = CoinMetricsConnector(cm_config)
    await cm.connect()
    metrics = await cm.get_latest_metrics()
    print(f"Price: ${metrics.payload['metrics']['PriceUSD']}")
    print(f"Active Addresses: {metrics.payload['metrics']['AdrActCnt']}")
    await cm.disconnect()

asyncio.run(main())
```

---

*Last Updated: February 18, 2026*
*All APIs verified with actual requests*
*Connectors implemented and tested*
