# Bitcoin On-Chain Metrics Implementation Plan

> **STATUS: COMPLETED** - All planned connectors have been implemented.
> This document is retained for reference and historical context.

## Executive Summary

This document outlines a comprehensive plan to expand Bitcoin on-chain metrics collection in the market-scraper system. The current implementation only includes CBBI (Colin Talks Crypto Bitcoin Bull Run Index). This plan proposes adding multiple data sources to capture essential on-chain metrics for trading analysis.

---

## Part 1: Essential Bitcoin On-Chain Metrics for Trading

### Category A: Valuation Metrics (Most Important)

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **MVRV Z-Score** | Market Value to Realized Value ratio | >7 = Top, <1 = Bottom | Critical |
| **NUPL** | Net Unrealized Profit/Loss | High = Distribution, Low = Accumulation | Critical |
| **SOPR** | Spent Output Profit Ratio | >1 = Profit taking, <1 = Capitulation | Critical |
| **Puell Multiple** | Miner revenue vs 365d MA | High = Top, Low = Bottom | Critical |
| **Realized Price** | Average cost basis of all BTC | Price below = Accumulation zone | High |
| **Reserve Risk** | Confidence of long-term holders | Low = Bullish, High = Bearish | High |

### Category B: Network Activity Metrics

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **Active Addresses** | Daily unique addresses | Increasing = Network growth | High |
| **Transaction Count** | Daily transactions | High activity = Strong demand | Medium |
| **Hash Rate** | Network security | Increasing = Miner confidence | High |
| **Difficulty** | Mining difficulty | Adjustments indicate miner behavior | Medium |
| **NVT Ratio** | Network Value to Transactions | High = Overvalued | High |

### Category C: Exchange Flow Metrics (Critical for Trading)

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **Exchange Reserve** | BTC held on exchanges | Decreasing = Bullish (withdrawal) | Critical |
| **Exchange Inflow** | BTC moving to exchanges | Increasing = Potential selling | Critical |
| **Exchange Outflow** | BTC leaving exchanges | Increasing = Hodling | Critical |
| **Netflow** | Inflow - Outflow | Negative = Bullish | Critical |

### Category D: Holder Behavior Metrics

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **HODL Waves** | Supply by age | LTH increasing = Accumulation | Medium |
| **Coin Days Destroyed (CDD)** | Long-term coins moving | Spikes = Old coins being sold | High |
| **Dormancy** | Average age of spent coins | High = Distribution | Medium |
| **LTH/STH Supply** | Long-term vs short-term holders | LTH selling = Top signal | High |

### Category E: Miner Metrics

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **Miner Reserve** | BTC held by miners | Decreasing = Miner selling | High |
| **Miner Outflow** | BTC sent by miners | Spikes = Potential selling pressure | High |
| **Hash Ribbons** | Hash rate MA crossover | Crossover = Miner capitulation/recovery | Medium |

### Category F: Sentiment Metrics

| Metric | Description | Trading Signal | Priority |
|--------|-------------|----------------|----------|
| **Fear & Greed Index** | Market sentiment | Extreme Fear = Buy, Extreme Greed = Sell | Medium |
| **Funding Rates** | Perpetual swap rates | High positive = Overleveraged longs | Medium |

---

## Part 2: Current Implementation Analysis

### What's Already Built

The codebase has a **CBBI Connector** that aggregates 9 Bitcoin on-chain metrics:

| Component | Description | Status |
|-----------|-------------|--------|
| PiCycle | Pi Cycle Top Indicator | ✅ Implemented |
| RUPL | Relative Unrealized Profit/Loss | ✅ Implemented |
| RHODL | Realized HODL Ratio | ✅ Implemented |
| Puell | Puell Multiple | ✅ Implemented |
| 2YMA | 2-Year Moving Average | ✅ Implemented |
| MVRV | MVRV Z-Score | ✅ Implemented |
| ReserveRisk | Reserve Risk | ✅ Implemented |
| Woobull | Top Cap vs CVDD | ✅ Implemented |
| Trolololo | Bitcoin Trolololo | ✅ Implemented |

### Architecture Pattern (to follow for new connectors)

```
src/market_scraper/connectors/{connector_name}/
├── __init__.py           # Package exports
├── config.py             # ConnectorConfig settings
├── client.py             # HTTP client implementation
├── parsers.py            # Data parsing functions
└── connector.py          # Main Connector class (extends DataConnector)
```

### Gaps in Current Implementation

| Missing Category | Metrics Not Available |
|-----------------|----------------------|
| Exchange Flows | Reserve, Inflow, Outflow, Netflow |
| Network Activity | Active Addresses, Transaction Count, Hash Rate |
| Holder Behavior | HODL Waves, CDD, Dormancy |
| Miner Metrics | Miner Reserve, Hash Ribbons |
| Sentiment | Fear & Greed Index, Funding Rates |
| Real-time Updates | CBBI is daily only |

---

## Part 3: API Source Analysis & Recommendations (VERIFIED)

> **Note:** All APIs below have been tested and verified on 2026-02-18 using browser automation.

### Primary Free APIs (VERIFIED ✅)

#### 1. Coin Metrics Community API ⭐⭐⭐⭐ (PARTIALLY FREE)

**Base URL:** `https://community-api.coinmetrics.io/v4`

**Pricing:** Free (no API key required)

**Rate Limits:** Not explicitly documented

**✅ VERIFIED FREE Metrics:**

| Metric ID | Description | Category | Status |
|-----------|-------------|----------|--------|
| `AdrActCnt` | Active Addresses | Network | ✅ FREE |
| `TxCnt` | Transaction Count | Network | ✅ FREE |
| `BlkCnt` | Block Count | Network | ✅ FREE |
| `CapMrktCurUSD` | Market Cap | Valuation | ✅ FREE |
| `SplyCur` | Current Supply | Supply | ✅ FREE |

**❌ REQUIRES PAID TIER:**

| Metric ID | Description | Category | Status |
|-----------|-------------|----------|--------|
| `CapMVRVZ` | MVRV Z-Score | Valuation | ❌ PAID |
| `CapRealUSD` | Realized Cap | Valuation | ❌ PAID |
| `DiffMean` | Mining Difficulty | Mining | ❌ PAID |

**Verified Endpoint:**
```
GET https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=AdrActCnt,TxCnt,BlkCnt&start_time=2026-02-17&end_time=2026-02-18

Response:
{"data":[{"asset":"btc","time":"2026-02-17T00:00:00.000000000Z","AdrActCnt":"595445","BlkCnt":"165","TxCnt":"661420"}]}
```

**Pros:**
- Completely free for basic metrics
- No API key needed
- High-quality institutional-grade data

**Cons:**
- MVRV, Realized Cap, Difficulty require paid tier
- Exchange flow data not available in free tier

---

#### 2. Blockchain.info Charts API ⭐⭐⭐⭐⭐ (FULLY FREE - RECOMMENDED)

**Base URL:** `https://api.blockchain.info/charts/`

**Pricing:** Free

**Rate Limits:** None observed

**✅ VERIFIED FREE Metrics (with historical data):**

| Endpoint | Description | Historical |
|----------|-------------|------------|
| `/charts/market-price` | BTC Price | ✅ Yes (`timespan=30days`) |
| `/charts/total-bitcoins` | Circulating Supply | ✅ Yes |
| `/charts/hash-rate` | Network Hash Rate | ✅ Yes |
| `/charts/mempool-count` | Mempool Transactions | ✅ Yes |
| `/charts/difficulty` | Mining Difficulty | ✅ Yes |
| `/charts/n-transactions` | Daily Transactions | ✅ Yes |
| `/charts/n-unique-addresses` | Unique Addresses | ✅ Yes |
| `/charts/market-cap` | Market Cap | ✅ Yes |
| `/charts/trade-volume` | Trade Volume | ✅ Yes |
| `/charts/blocks-size` | Blockchain Size | ✅ Yes |

**Verified Endpoint:**
```
GET https://api.blockchain.info/charts/market-price?timespan=30days&format=json

Response:
{"status":"ok","name":"Market Price (USD)","unit":"USD","period":"day",
 "values":[{"x":1768780800,"y":93665.1},{"x":1768867200,"y":92553.06},...]}
```

**Pros:**
- Completely free, no authentication
- Historical data with `timespan` parameter
- Real-time updates
- Multiple time resolutions

**Cons:**
- No advanced on-chain metrics (MVRV, SOPR, etc.)
- Basic network metrics only

---

#### 3. ResearchBitcoin.net API ⭐⭐⭐⭐⭐ (BEST FREE OPTION - RECOMMENDED)

**Base URL:** `https://api.thebitcoinresearcher.net/v2/`

**Pricing:**
- **Tier 0 (FREE):** 55,000 data points/week, 1 year historical
- Tier 1 (Paid): 900,000 DPs/week, unlimited historical
- Tier 2 (Paid): 40,000,000 DPs/week, unlimited historical

**✅ VERIFIED FREE Metrics (350+ available):**
- Requires free token registration at `https://api.researchbitcoin.net/v2/token`
- All metrics accessible in free tier (with limits)

**Key Metrics Available:**
- NUPL, SOPR, MVRV, Realized Price
- CDD, Dormancy, HODL Waves
- Hash Ribbons, Puell Multiple
- LTH/STH Supply
- And 340+ more metrics

**Verified Endpoint Pattern:**
```python
# From their demo script
GET https://api.thebitcoinresearcher.net/v2/unrealizedprofit/unrealized_profit_lth
Headers: {"X-API-Token": "your-token"}
Params: {"from_time": "2025-08-01 00:00", "to_time": "2025-08-02 00:00",
         "resolution": "h12", "output_format": "json"}
```

**Pros:**
- 350+ metrics for FREE
- Real-time block-level updates
- Multiple resolutions (h12, d1, etc.)
- JSON and CSV output

**Cons:**
- Requires free token registration
- 55,000 data points/week limit (generous for most uses)
- Newer service

---

#### 4. Alternative.me Fear & Greed Index ⭐⭐⭐⭐⭐ (FULLY FREE)

**Base URL:** `https://api.alternative.me/fng/`

**Pricing:** Free with attribution

**Rate Limits:** None specified

**✅ VERIFIED Endpoint:**
```
GET https://api.alternative.me/fng/?limit=10

Response:
{
  "name": "Fear and Greed Index",
  "data": [
    {
      "value": "40",
      "value_classification": "Fear",
      "timestamp": "1551157200",
      "time_until_update": "68499"
    }
  ],
  "metadata": {"error": null}
}
```

**Pros:**
- Completely free
- Historical data available (`limit=0` for all)
- Simple, reliable

**Cons:**
- Single metric only
- Updates once daily

---

#### 5. Glassnode Studio ⭐⭐⭐ (FREE TIER - NO API)

**Pricing:**
- **Studio Standard (FREE):** Basic metrics, 24h resolution, display only
- Studio Advanced ($49/mo): Essential metrics, 1h resolution
- Studio Professional ($999/mo): Full API access

**FREE Tier Includes:**
- Basic metrics (T1) catalog
- 24-hour metric resolution
- 1 custom alert

**Limitation:**
- ❌ **NO API ACCESS in free tier** (display only)
- API requires Professional subscription ($999/mo)

**Not Recommended for API implementation**

---

### Paid APIs (NOT VERIFIED - For Reference)

| API | Pricing | API Access | Notes |
|-----|---------|------------|-------|
| Bitbo | $588/year | ✅ Pro++ only | Comprehensive but expensive |
| Glassnode | $999/month | ✅ Pro only | Industry standard |
| CryptoQuant | $19-99/month | ✅ All tiers | Best for exchange flows |
| BGeometrics | ~$10-20/month | ✅ All tiers | Good coverage |

---

## Part 4: Recommended Implementation Strategy (FOCUSED)

> **Note:** CBBI already provides MVRV, RUPL, RHODL, Puell, 2YMA, ReserveRisk, PiCycle, Woobull, Trolololo.
> This plan focuses on **ADDING MISSING METRICS** only.

### What CBBI Already Covers ✅

| Metric | Description | Already Available |
|--------|-------------|-------------------|
| MVRV Z-Score | Market Value to Realized Value | ✅ CBBI |
| RUPL | Relative Unrealized Profit/Loss | ✅ CBBI |
| RHODL | Realized HODL Ratio | ✅ CBBI |
| Puell Multiple | Miner revenue ratio | ✅ CBBI |
| 2YMA | 2-Year Moving Average | ✅ CBBI |
| Reserve Risk | Long-term holder confidence | ✅ CBBI |
| PiCycle | Pi Cycle Top Indicator | ✅ CBBI |
| Woobull | Top Cap vs CVDD | ✅ CBBI |
| Trolololo | Logarithmic regression bands | ✅ CBBI |

### What's Still Missing ❌

| Metric | Category | Source | Priority |
|--------|----------|--------|----------|
| Hash Rate | Network | Blockchain.info | HIGH |
| Difficulty | Network | Blockchain.info | HIGH |
| Active Addresses | Network | Blockchain.info / Coin Metrics | HIGH |
| Transaction Count | Network | Blockchain.info / Coin Metrics | MEDIUM |
| Fear & Greed | Sentiment | Alternative.me | MEDIUM |
| Exchange Flows | Exchange | ❌ No free API | - |
| SOPR | Valuation | ❌ No free API | - |
| HODL Waves | Holder | ❌ No free API | - |
| CDD | Holder | ❌ No free API | - |

### Phase 1: Immediate Implementation (Week 1)

#### 1.1 BlockchainDotComConnector ⭐ PRIORITY 1
**Why:** Only free source for Hash Rate, Difficulty with historical data

**Metrics to Implement:**
```yaml
Verified FREE endpoints:
  - market-price: BTC price (historical with timespan)
  - hash-rate: Network hash rate (historical)
  - difficulty: Mining difficulty (historical)
  - total-bitcoins: Circulating supply
  - n-transactions: Daily transaction count
  - n-unique-addresses: Unique addresses
  - mempool-count: Mempool transactions
```

**API Endpoint Pattern:**
```
GET https://api.blockchain.info/charts/{metric}?timespan=30days&format=json
```

**File Structure:**
```
src/market_scraper/connectors/blockchain_com/
├── __init__.py
├── config.py
├── client.py
├── parsers.py
└── connector.py
```

#### 1.2 FearGreedConnector ⭐ PRIORITY 2
**Why:** Only free source for market sentiment, complements CBBI

**Metrics to Implement:**
- Fear & Greed Index (current + historical)

**API Endpoint:**
```
GET https://api.alternative.me/fng/?limit=0
```

**File Structure:**
```
src/market_scraper/connectors/fear_greed/
├── __init__.py
├── config.py
├── client.py
├── parsers.py
└── connector.py
```

### Phase 2: Optional Enhancement (Week 2)

#### 2.1 CoinMetricsConnector (Basic Metrics Only)
**Why:** Additional network metrics (limited free tier)

**FREE Metrics Available:**
- `AdrActCnt` - Active Addresses
- `TxCnt` - Transaction Count
- `BlkCnt` - Block Count
- `CapMrktCurUSD` - Market Cap
- `SplyCur` - Current Supply

**Note:** MVRV, Realized Cap, Difficulty are NOT free

### What We Cannot Get for Free ❌

The following metrics require paid APIs:
- **Exchange Flows** (Reserve, Inflow, Outflow) - CryptoQuant ($19+/mo), Glassnode ($999/mo)
- **SOPR** - Glassnode, ResearchBitcoin (paid)
- **HODL Waves** - Glassnode, Bitbo ($588/yr)
- **CDD/Dormancy** - Glassnode
- **Miner Reserves** - CryptoQuant

### Recommended Free Implementation Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BITCOIN ON-CHAIN DATA SOURCES                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │    CBBI         │  │ Blockchain.info │  │ Alternative.me  │     │
│  │   (existing)    │  │   (new)         │  │    (new)        │     │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤     │
│  │ • MVRV          │  │ • Hash Rate     │  │ • Fear & Greed  │     │
│  │ • RUPL          │  │ • Difficulty    │  │                 │     │
│  │ • RHODL         │  │ • Transactions  │  │                 │     │
│  │ • Puell         │  │ • Addresses     │  │                 │     │
│  │ • 2YMA          │  │ • Price         │  │                 │     │
│  │ • ReserveRisk   │  │ • Mempool       │  │                 │     │
│  │ • PiCycle       │  │ • Supply        │  │                 │     │
│  │ • Woobull       │  │                 │  │                 │     │
│  │ • Trolololo     │  │                 │  │                 │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    UNIFIED ON-CHAIN API                        │  │
│  │              GET /api/v1/onchain/btc/summary                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Unified On-Chain API (Week 5-6)

Create a unified API layer that aggregates all on-chain data:

```
src/market_scraper/processors/onchain_aggregator.py
src/market_scraper/api/routes/onchain.py
```

**New REST Endpoints:**
```
GET /api/v1/onchain/btc/summary          # All metrics combined
GET /api/v1/onchain/btc/valuation        # MVRV, NUPL, SOPR, etc.
GET /api/v1/onchain/btc/network          # Hash rate, difficulty, addresses
GET /api/v1/onchain/btc/exchange-flows   # Reserve, inflow, outflow
GET /api/v1/onchain/btc/miner            # Miner metrics
GET /api/v1/onchain/btc/sentiment        # Fear & Greed
```

---

## Part 5: Detailed Implementation Specifications

### 5.1 CoinMetrics Connector Implementation

```python
# src/market_scraper/connectors/coinmetrics/config.py

from market_scraper.connectors.base import ConnectorConfig
from pydantic import HttpUrl

class CoinMetricsConfig(ConnectorConfig):
    """Coin Metrics connector configuration."""

    base_url: HttpUrl = "https://community-api.coinmetrics.io/v4"
    api_key: str | None = None  # Optional for pro tier
    update_interval_seconds: int = 3600  # 1 hour
    historical_days: int = 365

    # Metrics to fetch
    metrics: list[str] = [
        "CapMVRVZ",        # MVRV Z-Score
        "CapRealUSD",      # Realized Cap
        "AdrActCnt",       # Active Addresses
        "TxCnt",           # Transaction Count
        "DiffMean",        # Difficulty
        "BlkIntMean",      # Block Interval
        "SplyCur",         # Current Supply
    ]
```

```python
# src/market_scraper/connectors/coinmetrics/client.py

import httpx
import structlog
from typing import Any

logger = structlog.get_logger(__name__)

class CoinMetricsClient:
    """HTTP client for Coin Metrics Community API."""

    def __init__(self, config: CoinMetricsConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._base_url = str(config.base_url).rstrip("/")

    async def connect(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("coinmetrics_client_connected")

    async def get_asset_metrics(
        self,
        asset: str = "btc",
        metrics: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """Fetch asset metrics timeseries.

        Args:
            asset: Asset symbol (btc, eth, etc.)
            metrics: List of metric IDs
            start_time: ISO 8601 start time
            end_time: ISO 8601 end time

        Returns:
            Raw API response
        """
        if metrics is None:
            metrics = self.config.metrics

        params = {
            "assets": asset,
            "metrics": ",".join(metrics),
        }

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        response = await self._client.get(
            f"{self._base_url}/timeseries/asset-metrics",
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def get_reference_metrics(self) -> list[dict]:
        """Fetch all available metric definitions."""
        response = await self._client.get(
            f"{self._base_url}/reference-data/asset-metrics"
        )
        response.raise_for_status()
        return response.json().get("data", [])
```

### 5.2 Fear & Greed Connector Implementation

```python
# src/market_scraper/connectors/fear_greed/config.py

from market_scraper.connectors.base import ConnectorConfig
from pydantic import HttpUrl

class FearGreedConfig(ConnectorConfig):
    """Fear & Greed Index connector configuration."""

    base_url: HttpUrl = "https://api.alternative.me/fng"
    update_interval_seconds: int = 3600  # 1 hour
    historical_limit: int = 0  # 0 = all available data
```

```python
# src/market_scraper/connectors/fear_greed/client.py

import httpx
import structlog
from typing import Any

logger = structlog.get_logger(__name__)

class FearGreedClient:
    """HTTP client for Alternative.me Fear & Greed API."""

    def __init__(self, config: FearGreedConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._base_url = str(config.base_url).rstrip("/")

    async def connect(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(timeout=30.0)
        logger.info("fear_greed_client_connected")

    async def get_index_data(self, limit: int = 0) -> dict[str, Any]:
        """Fetch Fear & Greed Index data.

        Args:
            limit: Number of results (0 = all available)

        Returns:
            API response with index data
        """
        params = {"limit": limit} if limit > 0 else {}

        response = await self._client.get(self._base_url, params=params)
        response.raise_for_status()
        return response.json()
```

### 5.3 Unified On-Chain Data Model

```python
# src/market_scraper/core/types/onchain.py

from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class OnChainMetric(BaseModel):
    """Standardized on-chain metric data."""

    metric_name: str
    metric_category: Literal[
        "valuation", "network", "exchange_flow",
        "miner", "holder", "sentiment"
    ]
    value: float
    timestamp: datetime
    source: str  # "coinmetrics", "blockchain_com", "cbbi", etc.
    unit: str | None = None  # "USD", "BTC", "count", "ratio"
    change_24h: float | None = None
    change_7d: float | None = None

class BitcoinOnChainSummary(BaseModel):
    """Aggregated Bitcoin on-chain metrics."""

    timestamp: datetime
    price_usd: float

    # Valuation
    mvrv_z_score: OnChainMetric | None = None
    nupl: OnChainMetric | None = None
    sopr: OnChainMetric | None = None
    puell_multiple: OnChainMetric | None = None
    realized_price: OnChainMetric | None = None

    # Network
    active_addresses: OnChainMetric | None = None
    transaction_count: OnChainMetric | None = None
    hash_rate: OnChainMetric | None = None
    difficulty: OnChainMetric | None = None

    # Exchange Flows
    exchange_reserve: OnChainMetric | None = None
    exchange_inflow: OnChainMetric | None = None
    exchange_outflow: OnChainMetric | None = None

    # Sentiment
    fear_greed_index: OnChainMetric | None = None
    cbbi_confidence: OnChainMetric | None = None
```

---

## Part 6: API Endpoints Specification

### New REST Endpoints

#### GET /api/v1/onchain/btc/summary

Returns aggregated on-chain summary with all available metrics.

```json
{
  "timestamp": "2026-02-18T00:00:00Z",
  "price_usd": 95000,
  "valuation": {
    "mvrv_z_score": {"value": 2.5, "change_24h": 0.1, "signal": "neutral"},
    "nupl": {"value": 0.45, "signal": "optimism"},
    "sopr": {"value": 1.02, "signal": "profit_taking"}
  },
  "network": {
    "active_addresses": {"value": 850000, "change_24h": 2.5},
    "hash_rate": {"value": 650000000, "unit": "TH/s"}
  },
  "exchange_flows": {
    "reserve": {"value": 2400000, "change_7d": -50000, "signal": "bullish"}
  },
  "sentiment": {
    "fear_greed_index": {"value": 55, "classification": "Greed"},
    "cbbi_confidence": {"value": 0.45}
  }
}
```

#### GET /api/v1/onchain/btc/metrics/{metric_name}

Returns historical data for a specific metric.

```json
{
  "metric_name": "mvrv_z_score",
  "current_value": 2.5,
  "historical": [
    {"timestamp": "2026-02-18", "value": 2.5},
    {"timestamp": "2026-02-17", "value": 2.4},
    ...
  ],
  "statistics": {
    "mean_30d": 2.3,
    "std_30d": 0.3,
    "max_365d": 7.2,
    "min_365d": 0.8
  }
}
```

---

## Part 7: Testing Strategy

### Unit Tests

```python
# tests/connectors/test_coinmetrics.py

import pytest
from market_scraper.connectors.coinmetrics import CoinMetricsConnector, CoinMetricsConfig

@pytest.fixture
def coinmetrics_config():
    return CoinMetricsConfig(name="coinmetrics")

@pytest.fixture
def coinmetrics_connector(coinmetrics_config):
    return CoinMetricsConnector(coinmetrics_config)

@pytest.mark.asyncio
async def test_coinmetrics_connect(coinmetrics_connector):
    await coinmetrics_connector.connect()
    # Assert client is initialized

@pytest.mark.asyncio
async def test_coinmetrics_get_metrics(coinmetrics_connector):
    await coinmetrics_connector.connect()
    metrics = await coinmetrics_connector.get_metrics(asset="btc")
    assert "CapMVRVZ" in metrics
    assert len(metrics["CapMVRVZ"]) > 0
```

### Integration Tests

```python
# tests/integration/test_onchain_api.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_onchain_summary_endpoint():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.get("/api/v1/onchain/btc/summary")
        assert response.status_code == 200
        data = response.json()
        assert "valuation" in data
        assert "network" in data
```

---

## Part 8: Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting | Medium | Medium | Implement request caching, use multiple sources |
| API downtime | Low | High | Fallback to alternative sources, circuit breaker |
| Data inconsistency | Medium | Medium | Cross-validate with multiple sources |
| Historical data gaps | Low | Low | Cache data locally, backfill from multiple sources |

---

## Part 9: Implementation Checklist

### Phase 1: Core Connectors
- [x] Create CoinMetrics connector
  - [x] config.py
  - [x] client.py
  - [x] parsers.py
  - [x] connector.py
  - [x] Unit tests
- [x] Create BlockchainInfo connector
  - [x] config.py
  - [x] client.py
  - [x] parsers.py
  - [x] connector.py
  - [x] Unit tests
- [x] Create Fear & Greed connector
  - [x] config.py
  - [x] client.py
  - [x] parsers.py
  - [x] connector.py
  - [x] Unit tests
- [x] Create ChainExposed connector
  - [x] config.py
  - [x] client.py
  - [x] parsers.py
  - [x] connector.py
  - [x] Unit tests
- [x] Create ExchangeFlow connector
  - [x] config.py
  - [x] client.py
  - [x] parsers.py
  - [x] connector.py
  - [x] Unit tests

### Phase 2: Enhanced Metrics
- [ ] Create ResearchBitcoin connector (optional - requires API token)
- [ ] (Optional) Create BGeometrics connector with API key

### Phase 3: Unified API
- [x] Create OnChainAggregator processor
- [x] Create unified /api/v1/onchain routes
- [x] Update documentation
- [x] Integration tests

---

## References

- [Coin Metrics API Docs](https://docs.coinmetrics.io/api/v4/)
- [Blockchain.com API](https://www.blockchain.com/explorer/api/q)
- [Alternative.me FNG API](https://alternative.me/crypto/fear-and-greed-index/)
- [BGeometrics API](https://bitcoin-data.com/api/redoc.html)
- [ResearchBitcoin API](https://api.researchbitcoin.net/)
- [Glassnode Docs](https://docs.glassnode.com/)

---

*Document Version: 1.0*
*Created: February 2026*
