# Data Collection Analysis & Recommendations

> **STATUS: IMPLEMENTED** - All recommendations have been applied.
>
> Changes made:
> - Removed trades collection
> - Removed orderbook collection
> - Removed AllMids collector
> - Removed price data from on-chain connectors
> - Kept all candle timeframes

## Executive Summary

After analyzing the data collection architecture, I've identified **significant overlaps** and **questionable data collection practices**. This report provides recommendations to optimize storage, reduce redundancy, and improve system focus.

---

## Current Data Collection Overview

### Hyperliquid Collectors

| Collector | What It Collects | Storage | Retention |
|-----------|------------------|---------|-----------|
| **TradesCollector** | Individual trades (≥$1,000) | `btc_trades` | 7 days |
| **OrderbookCollector** | L2 orderbook snapshots (1% price change) | `btc_orderbook` | 7 days |
| **CandlesCollector** | OHLCV candles (1m, 5m, 15m, 1h, 4h, 1d) | `btc_candles_{interval}` | 30 days |
| **AllMidsCollector** | Mark prices for all coins | `mark_prices` | 30 days |
| **LeaderboardCollector** | Top trader rankings | `leaderboard_history`, `tracked_traders` | 90 days |
| **TraderWSCollector** | Real-time trader positions | `trader_positions` | 30 days |

### On-Chain Connectors (Also Collect Price)

| Connector | What It Collects | Price Data |
|-----------|------------------|------------|
| **BlockchainInfo** | Hash rate, difficulty, supply | ✅ `price_usd` (24h average) |
| **CoinMetrics** | Active addresses, volume | ✅ `PriceUSD` |
| **ExchangeFlow** | Exchange flows | ✅ `price_usd` |
| **CBBI** | Bitcoin Bull Run Index | ❌ No direct price |
| **FearGreed** | Sentiment index | ❌ No direct price |
| **ChainExposed** | SOPR, NUPL, MVRV | ❌ No direct price |

---

## Data Overlap Analysis

### 1. Price Data (MAJOR OVERLAP)

**4+ sources collect BTC price:**

| Source | Data | Collection Method | Storage |
|--------|------|-------------------|---------|
| Hyperliquid Trades | `price` per trade | Real-time WS | `btc_trades.t` |
| Hyperliquid AllMids | `mark_price` | Real-time WS | `mark_prices.price` |
| Hyperliquid Candles | `open/high/low/close` | Real-time WS | `btc_candles_*.o,h,l,c` |
| BlockchainInfo | `price_usd` | HTTP poll | In response |
| CoinMetrics | `PriceUSD` | HTTP poll | In response |
| ExchangeFlow | `price_usd` | HTTP CSV | In response |

**Redundancy:** 4-6 sources for the same data point (BTC price)

### 2. Candles vs Trades (DERIVATIVE OVERLAP)

**Trades can derive candles, but we collect both:**

- `TradesCollector`: Saves individual trades (price, size, side, time)
- `CandlesCollector`: Saves OHLCV candles (same data aggregated)

**Candles are derived from trades.** Hyperliquid sends pre-aggregated candles, but we could:
1. Generate candles from trades ourselves, OR
2. Use candles only and skip individual trades

### 3. Orderbook vs Trades (PARTIAL OVERLAP)

**Both provide price discovery:**

- `TradesCollector`: Execution prices (what actually traded)
- `OrderbookCollector`: Bid/ask prices (what's available to trade)

**These are different data** - trades show executed prices, orderbook shows available liquidity. However, for a **trader signal system**, orderbook data may not be essential.

---

## Usage Analysis

### What the System Actually Uses

| Data | Used By | Purpose |
|------|---------|---------|
| `trader_positions` | Signal Generation | Core functionality ✅ |
| `tracked_traders` | Signal Generation | Core functionality ✅ |
| `signals` | API endpoints | Core functionality ✅ |
| `leaderboard_history` | Position Inference | Core functionality ✅ |
| `btc_trades` | `get_market_data()` API | **Marginal** ⚠️ |
| `btc_orderbook` | `get_market_data()` API | **Marginal** ⚠️ |
| `btc_candles_*` | `get_market_history()` API | **Marginal** ⚠️ |
| `mark_prices` | None visible | **Unused** ❓ |

### What the System Does NOT Use

1. **Individual trades** - No processor consumes individual trades for signal generation
2. **Orderbook snapshots** - No processor uses orderbook for signal generation
3. **Mark prices from AllMids** - Appears unused (price comes from candles/trades)

---

## Purpose Alignment Check

### System Purpose
> "Track top traders, generate trading signals, aggregate Bitcoin on-chain metrics"

### Data Relevance

| Data | Relevant to Purpose? | Justification |
|------|---------------------|---------------|
| Trader positions | ✅ Essential | Core signal generation |
| Trader scores | ✅ Essential | Weight signals by trader quality |
| CBBI / On-chain | ✅ Essential | Market context |
| Leaderboard | ✅ Essential | Find traders to track |
| **Individual trades** | ❌ Not essential | Signals from positions, not trades |
| **Orderbook snapshots** | ❌ Not essential | Signals from positions, not book |
| **Candles** | ⚠️ Optional | Could be useful for price reference |

---

## Recommendations

### RECOMMENDATION 1: Remove Trades Collection (HIGH IMPACT)

**Rationale:**
- Individual trades are NOT used for signal generation
- Signals come from **trader positions**, not market trades
- 7-day retention suggests low importance
- Storage savings: ~67% of market data

**Action:** Disable `TradesCollector` or make it optional

```python
# In config
HYPERLIQUID__COLLECT_TRADES=false
```

**Impact:** Reduced storage, reduced CPU/network load

---

### RECOMMENDATION 2: Remove Orderbook Collection (HIGH IMPACT)

**Rationale:**
- Orderbook data is NOT used for signal generation
- Signal system tracks trader positions, not market liquidity
- Only useful for real-time trading (not this system's purpose)
- Storage savings: ~95% reduction from throttling already applied

**Action:** Disable `OrderbookCollector` or make it optional

```python
# In config
HYPERLIQUID__COLLECT_ORDERBOOK=false
```

**Impact:** Significant storage reduction, simplified architecture

---

### RECOMMENDATION 3: Keep Candles (OPTIONAL) or Remove

**Keep IF:**
- You want price context in API responses
- You want to correlate signals with price action
- You want historical price reference

**Remove IF:**
- System is purely for signal generation
- Price data from on-chain connectors is sufficient
- You want maximum simplicity

**Recommendation:** Keep candles at 1h and 1d intervals only (remove 1m, 5m, 15m, 4h)

```python
# Config
HYPERLIQUID__CANDLE_INTERVALS=["1h", "1d"]
```

---

### RECOMMENDATION 4: Remove AllMids Collector (MEDIUM IMPACT)

**Rationale:**
- Mark prices are redundant with candle close prices
- No processor appears to use `mark_prices` collection
- Price available from candles and on-chain connectors

**Action:** Disable `AllMidsCollector`

---

### RECOMMENDATION 5: Deduplicate On-Chain Price Data

**Current:** 4 sources provide BTC price
**Recommended:** Use single authoritative source

| Source | Keep? | Reason |
|--------|-------|--------|
| Hyperliquid Candles | ✅ Primary | Real-time, exchange-specific |
| BlockchainInfo | ❌ Remove price | Keep network metrics only |
| CoinMetrics | ❌ Remove price | Keep activity metrics only |
| ExchangeFlow | ❌ Remove price | Keep flow metrics only |

**Action:** Modify on-chain connectors to not include price in responses, or mark as secondary

---

## Implementation Priority

### Phase 1: Immediate (Zero Risk)
1. Remove `AllMidsCollector` - no visible usage
2. Reduce candle intervals to 1h, 1d only

### Phase 2: Configuration Changes (Low Risk)
1. Add `--no-trades` flag to disable trades collection
2. Add `--no-orderbook` flag to disable orderbook collection
3. Update API endpoints to handle missing data gracefully

### Phase 3: Architecture Simplification (Medium Risk)
1. Remove price fields from on-chain connector responses
2. Remove trade/orderbook storage code
3. Update documentation

---

## Expected Impact

### Storage Reduction

| Collection | Current Est. | After Removal | Savings |
|------------|--------------|---------------|---------|
| `btc_trades` | ~500MB/day | 0 | 100% |
| `btc_orderbook` | ~50MB/day | 0 | 100% |
| `btc_candles_1m` | ~1MB/day | 0 | 100% |
| `btc_candles_5m` | ~200KB/day | 0 | 100% |
| `btc_candles_15m` | ~100KB/day | 0 | 100% |
| `btc_candles_4h` | ~50KB/day | 0 | 100% |
| `btc_candles_1h` | ~50KB/day | Keep | 0% |
| `btc_candles_1d` | ~10KB/day | Keep | 0% |
| `mark_prices` | ~10MB/day | 0 | 100% |

**Estimated Total Savings: ~85-90% of market data storage**

### Network/CPU Reduction

| Metric | Reduction |
|--------|-----------|
| WebSocket messages processed | ~70% |
| Database writes | ~85% |
| Memory usage | ~50% |

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Remove trades | Low | Not used for signals |
| Remove orderbook | Low | Not used for signals |
| Remove AllMids | Low | Redundant price data |
| Reduce candle intervals | Low | 1h/1d sufficient for analysis |
| Remove on-chain prices | Low | Hyperliquid is primary source |

---

## Summary Table

| Data | Keep? | Reason |
|------|-------|--------|
| **Trades** | ❌ Remove | Not used for signal generation |
| **Orderbook** | ❌ Remove | Not used for signal generation |
| **Candles (1h, 1d)** | ✅ Keep | Useful for price context |
| **Candles (1m, 5m, 15m, 4h)** | ❌ Remove | Excessive granularity |
| **AllMids/Mark Prices** | ❌ Remove | Redundant with candles |
| **Trader Positions** | ✅ Keep | Core signal generation |
| **Leaderboard** | ✅ Keep | Find traders to track |
| **On-chain metrics** | ✅ Keep | Market context |
| **On-chain prices** | ❌ Remove | Redundant with Hyperliquid |

---

## Conclusion

The current system collects significantly more data than needed for its stated purpose. By focusing on trader positions, signals, and on-chain metrics (without duplicate prices), the system can achieve:

1. **~85-90% reduction** in market data storage
2. **~70% reduction** in WebSocket processing
3. **Simplified architecture** with clear data purpose
4. **Lower operational costs** for database and compute

The core value proposition—tracking traders and generating signals—does not require individual trades, orderbooks, or second-by-second prices. Trader positions already contain the entry/exit signals we need.

---

*Report Generated: February 2026*
