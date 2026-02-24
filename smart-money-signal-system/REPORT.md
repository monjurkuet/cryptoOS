# Smart Money Signal System - Comprehensive Report

**Generated**: 2026-02-24
**Status**: Planning Phase
**Target**: BTC Signal Generation from Hyperliquid Trader Data

---

## Executive Summary

This report outlines a comprehensive approach to generating trading signals for BTC by:

1. **Tracking real trader positions** from Hyperliquid (no inference needed)
2. **Weighting traders** based on multi-dimensional criteria
3. **Aggregating positions** into actionable signals
4. **Integrating on-chain metrics** for market context
5. **Using ML selectively** for discovery, not signal generation

**Critical Discovery**: Hyperliquid exposes actual trader positions via the `webData2` API, including position direction (long/short), size, entry price, unrealized PnL, and leverage. The `TraderWebSocketCollector` exists in the codebase but is disabled.

---

## Table of Contents

1. [Current System State](#current-system-state)
2. [Available Data Sources](#available-data-sources)
3. [Wallet Monitoring Strategy](#wallet-monitoring-strategy)
4. [Wallet Weighting Criteria](#wallet-weighting-criteria)
5. [Machine Learning Appropriateness](#machine-learning-appropriateness)
6. [Signal Generation Strategies](#signal-generation-strategies)
7. [Research Findings](#research-findings)
8. [Recommendations](#recommendations)

---

## 1. Current System State

### Working Components

| Component | Status | Data Available |
|-----------|--------|----------------|
| Candles Collector | Running | Real-time BTC OHLCV |
| Leaderboard Collector | Running | 500 top traders, scores, tags |
| CBBI Connector | Working | 9-component bull run index |
| On-chain Connectors | Working | SOPR, MVRV, NUPL, Fear/Greed, etc. |
| Trader Scoring | Working | Multi-factor scoring with tags |

### Not Working / Disabled

| Component | Status | Issue |
|-----------|--------|-------|
| `TraderWebSocketCollector` | Not started | Exists but disabled in manager |
| `trader_positions` events | Never emitted | Collector not running |
| Signal Generation | Empty signals | No position data to process |

### Root Cause

```python
# lifecycle.py:443
collectors=["candles"],  # Only candles collector implemented currently

# manager.py:66-68
collector_classes = {
    "candles": CandlesCollector,
    # TraderWebSocketCollector is NOT registered here!
}
```

---

## 2. Available Data Sources

### 2.1 Trader Position Data (Real-Time via WebSocket)

**API Endpoint**: `POST https://api.hyperliquid.xyz/info`
**Request**: `{"type": "webData2", "user": "0x..."}`

**Sample Response** (BobbyBigSize - top trader):
```json
{
  "clearinghouseState": {
    "marginSummary": {
      "accountValue": "32494836.19",
      "totalNtlPos": "83895370.21"
    },
    "assetPositions": [
      {
        "position": {
          "coin": "BTC",
          "szi": "-353.37336",
          "entryPx": "67707.8",
          "positionValue": "22331429.48",
          "unrealizedPnl": "1594707.94",
          "leverage": { "value": 20 },
          "liquidationPx": "148286.12"
        }
      }
    ]
  }
}
```

**Data Fields**:

| Field | Meaning | Use Case |
|-------|---------|----------|
| `szi` | Position size (negative=short, positive=long) | Direction signal |
| `szi` absolute | Position size in BTC | Weighting |
| `entryPx` | Entry price | Profit calculation |
| `unrealizedPnl` | Current P&L | Trader performance |
| `leverage.value` | Leverage used | Risk assessment |
| `positionValue` | USD position value | Market impact |
| `accountValue` | Total account value | Trader tier |

### 2.2 Leaderboard Data (5-minute refresh)

| Field | Example | Use Case |
|-------|---------|----------|
| `ethAddress` | `0x7fdafd...` | Trader identification |
| `accountValue` | `$35,127,898` | Whale detection |
| `windowPerformances` | Day/Week/Month/All ROI | Trader scoring |
| `displayName` | `BobbyBigSize` | Display |

### 2.3 On-Chain Metrics (Daily)

| Source | Metrics | Current Value |
|--------|---------|---------------|
| CBBI | Confidence, 9 components | 0.3054 |
| Fear & Greed | Sentiment score | 8 (Extreme Fear) |
| Bitview | SOPR, STH-SOPR, LTH-SOPR, MVRV, NUPL | SOPR: 0.986 |
| Coin Metrics | Exchange flows, active addresses | Netflow: +614 BTC |
| Blockchain.info | Hashrate, difficulty, block height | Block: 938,085 |

---

## 3. Wallet Monitoring Strategy

### Research Findings on Optimal Numbers

| Source | Recommendation | Rationale |
|--------|----------------|-----------|
| TradeFundrr (2025) | 3-5 traders for copy trading | Optimal diversification |
| Diversified Copy Trading Guide | Minimum 3-5, max 20-25% per trader | Risk distribution |
| Stock Portfolio Theory | 10-30 stocks for 90%+ diversification | Diminishing returns after ~20 |
| Crypto Whale Trackers | Focus on top 100-500 wallets | Smart money concentration |

### Recommended Tiered Approach

```
Tier 1: WHALE ALERTS (20-30 wallets)
- Individual tracking for real-time alerts
- Criteria: Account >=$10M OR Score >=100
- Purpose: Immediate whale switch detection

Tier 2: SIGNAL CORE (100-150 wallets)
- Primary signal generation cohort
- Criteria: Score >=70, consistent positive ROI
- Purpose: Weighted aggregate position bias

Tier 3: SIGNAL EXTENDED (200-300 wallets)
- Broader market sentiment tracking
- Criteria: Score >=50, in top 500 leaderboard
- Purpose: Confirmation signal, retail divergence

TOTAL ACTIVE MONITORING: 300-500 wallets
```

### Why 300-500 is Optimal

1. **Statistical Significance**: With ~475 traders having BTC positions, reliable aggregate bias
2. **Market Coverage**: Top 500 on Hyperliquid represents significant market influence
3. **WebSocket Limits**: 500 traders x 5 concurrent connections = manageable load
4. **Noise Filtering**: Large sample size smooths out individual noise
5. **Divergence Detection**: Can detect when elite traders diverge from broader market

---

## 4. Wallet Weighting Criteria

### Current vs Recommended Approach

**Current Scoring** (in `trader_scoring.py`):
- All-time ROI: 30%
- Month ROI: 25%
- Week ROI: 20%
- Account Value: 15%
- Volume: 10%
- Consistency Bonus: +5%

**Issue**: This is a performance ranking, not a signal weighting system.

### Recommended: Multi-Dimensional Weighting

#### Dimension 1: Performance Weight (Signal Quality)

| Metric | Weight | Why It Matters |
|--------|--------|----------------|
| Sharpe Ratio | 25% | Risk-adjusted returns |
| Sortino Ratio | 20% | Downside risk focus |
| Consistency Score | 20% | Positive ROI across all timeframes |
| Max Drawdown | 15% | Risk tolerance (inverse) |
| Win Rate | 10% | Trade accuracy |
| Profit Factor | 10% | Gross profit / gross loss |

**Formulas**:
- Sharpe Ratio = (Return - Risk Free Rate) / Standard Deviation
- Sortino Ratio = (Return - Risk Free Rate) / Downside Deviation
- Profit Factor = Gross Wins / Gross Losses

#### Dimension 2: Size Weight (Market Impact)

| Tier | Account Value | Weight Multiplier |
|------|---------------|-------------------|
| Alpha Whale | >=$20M | 3.0x |
| Whale | $10M-$20M | 2.5x |
| Large | $5M-$10M | 2.0x |
| Medium | $1M-$5M | 1.5x |
| Standard | $100K-$1M | 1.0x |
| Small | <$100K | 0.5x |

#### Dimension 3: Recency Weight (Temporal Decay)

```python
def calculate_recency_weight(trader: dict) -> float:
    """
    Weight more recent performance higher.
    """
    day_roi = get_roi(trader, "day")
    week_roi = get_roi(trader, "week")
    month_roi = get_roi(trader, "month")

    # Exponential decay: day > week > month
    recency_score = (
        day_roi * 0.50 +    # 50% weight
        week_roi * 0.30 +   # 30% weight
        month_roi * 0.20    # 20% weight
    )

    # Normalize to 0.5 - 1.5 range
    return 0.5 + (recency_score * 0.5)
```

#### Dimension 4: Regime Alignment Weight

```python
def calculate_regime_alignment(trader: dict, market_regime: str) -> float:
    """
    Weight traders higher who perform well in current market regime.
    """
    if market_regime == "high_volatility":
        return trader.get("volatility_adjusted_score", 1.0)
    elif market_regime == "trending":
        return trader.get("trend_performance_score", 1.0)
    elif market_regime == "ranging":
        return trader.get("range_performance_score", 1.0)
    return 1.0
```

### Final Composite Weight Formula

```python
def calculate_composite_weight(trader: dict, market_regime: str) -> float:
    # Dimension 1: Performance Quality (0-100 scale)
    performance_weight = calculate_performance_weight(trader)

    # Dimension 2: Market Impact (0.5-3.0 scale)
    size_weight = calculate_size_weight(trader)

    # Dimension 3: Recency (0.5-1.5 scale)
    recency_weight = calculate_recency_weight(trader)

    # Dimension 4: Regime Alignment (0.8-1.2 scale)
    regime_weight = calculate_regime_alignment(trader, market_regime)

    # Composite weight
    composite = (
        performance_weight * 0.40 +
        size_weight * 0.30 +
        recency_weight * 0.20 +
        regime_weight * 0.10
    )

    return composite
```

### Weight Distribution Example

| Trader | Performance | Size | Recency | Regime | Composite |
|--------|-------------|------|---------|--------|-----------|
| BobbyBigSize | 95 | 3.0 | 1.3 | 1.1 | **2.42** |
| Alpha Whale #2 | 88 | 3.0 | 1.1 | 1.0 | **2.24** |
| Elite Trader | 85 | 1.5 | 1.2 | 1.1 | **1.68** |
| Consistent Performer | 80 | 1.0 | 1.0 | 1.0 | **1.20** |
| New High Performer | 75 | 1.0 | 1.4 | 0.9 | **1.15** |
| Standard Trader | 60 | 1.0 | 0.8 | 1.0 | **0.80** |

---

## 5. Machine Learning Appropriateness

### Analysis Matrix

| Aspect | Traditional Approach | ML Approach | Recommendation |
|--------|---------------------|-------------|----------------|
| Weight Allocation | Fixed rules | Dynamic learning | **Traditional** |
| Trader Selection | Threshold filters | Classification model | **Traditional** |
| Signal Generation | Weighted average | Neural network | **Traditional** |
| Regime Detection | Rule-based | Unsupervised clustering | **ML is valuable** |
| Feature Discovery | Manual | Feature importance | **ML is valuable** |
| Performance Prediction | Past performance | Predictive model | **ML could help** |

### When ML IS Appropriate

#### 1. Feature Importance Discovery (High Value)

```python
from sklearn.ensemble import RandomForestClassifier

features = [
    "sharpe_ratio", "sortino_ratio", "max_drawdown", "win_rate",
    "profit_factor", "avg_trade_duration", "position_concentration",
    "leverage_usage", "correlation_to_market", "performance_persistence"
]

# Train model to predict: Will this trader be profitable next month?
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Get feature importance
importance = pd.Series(model.feature_importances_, index=features)
```

**Expected Output**:
```
performance_persistence    0.23
sharpe_ratio               0.18
max_drawdown              0.15
sortino_ratio             0.12
win_rate                  0.10
profit_factor             0.08
```

#### 2. Market Regime Detection (High Value)

```python
from sklearn.cluster import KMeans

# Cluster on-chain metrics to identify market regimes
features = ["cbbi", "fear_greed", "sopr", "mvrv", "nupl", "volatility"]
X = prepare_regime_features(features)

# Identify 4-5 market regimes
kmeans = KMeans(n_clusters=5, random_state=42)
regimes = kmeans.fit_predict(X)
```

#### 3. Trader Clustering (Medium Value)

```python
# Cluster traders by behavior patterns
trader_features = [
    "avg_leverage", "position_holding_time", "trade_frequency",
    "correlation_to_btc", "pnl_volatility", "win_rate"
]

kmeans = KMeans(n_clusters=5)
trader_clusters = kmeans.fit_predict(trader_features)
```

### When ML is NOT Appropriate

#### 1. Signal Weight Calculation
**Why**:
- Fixed rules are interpretable and auditable
- No historical "ground truth" for optimal weights
- Risk of overfitting to past data
- Alpha decay - patterns that worked before stop working

#### 2. Position Direction Prediction
**Why**:
- Position data is factual, not something to "predict"
- The signal comes FROM positions, not predicting them
- ML adds complexity without benefit

### Research-Backed Insights

- **Performance Persistence**: ~30-40% of top traders remain top performers year-over-year
- **Alpha Decay**: Edge typically decays 20-40% within 6-12 months
- **Recency Bias**: Recent 3-month performance is more predictive than all-time
- **Regime Sensitivity**: Different traders excel in different market conditions

### Recommended: Hybrid Approach

```
ML COMPONENTS (Quarterly Retraining)
- Feature Importance: Discover predictive metrics
- Regime Detection: Identify market phase
- Trader Clustering: Group by behavior
- Anomaly Detection: Flag unusual behavior

RULES COMPONENTS (Human-Defined)
- Weight Allocation: Use discovered importance
- Trader Filtering: Min score, max drawdown
- Signal Generation: Weighted aggregation
- Alert Triggers: Whale switches, consensus flips

FEEDBACK LOOP
- Track signal accuracy weekly
- Retrain ML models monthly
- Adjust weights quarterly
```

---

## 6. Signal Generation Strategies

### Strategy 1: Smart Money Position Tracking (Primary)

**Concept**: Aggregate weighted positions of top traders to determine market direction.

#### Signal Calculation

```python
def calculate_smart_money_signal(traders: list) -> Signal:
    weighted_long = 0.0
    weighted_short = 0.0
    total_weight = 0.0

    for trader in traders:
        tier_weight = get_tier_weight(trader)
        btc_position = trader.get_btc_position()

        if not btc_position:
            continue

        szi = float(btc_position["szi"])
        position_value = abs(float(btc_position["positionValue"]))

        effective_weight = tier_weight * (position_value / 1_000_000)

        if szi > 0:
            weighted_long += effective_weight
        elif szi < 0:
            weighted_short += effective_weight

        total_weight += effective_weight

    long_bias = weighted_long / total_weight
    short_bias = weighted_short / total_weight
    net_bias = long_bias - short_bias

    if net_bias > 0.2:
        action = "BUY"
    elif net_bias < -0.2:
        action = "SELL"
    else:
        action = "NEUTRAL"

    return Signal(action=action, confidence=calculate_confidence(...))
```

### Strategy 2: Whale Switch Detection (Alert System)

**Alert Types**:

| Priority | Trigger | Response Time |
|----------|---------|---------------|
| CRITICAL | Alpha Whale ($20M+) changes BTC position | < 1 second |
| HIGH | 2+ whales change position within 5 min | < 5 seconds |
| MEDIUM | Aggregate whale bias flips sign | < 30 seconds |
| LOW | Elite consensus shifts 20%+ | < 1 minute |

### Strategy 3: On-Chain Market Regime

| Regime | CBBI | Fear/Greed | SOPR | Interpretation |
|--------|------|------------|------|----------------|
| Deep Accumulation | < 0.20 | < 20 | < 0.98 | Strong BUY zone |
| Early Bull | 0.20-0.40 | 20-40 | 0.98-1.02 | Accumulate |
| Mid Bull | 0.40-0.60 | 40-60 | 1.02-1.05 | Hold/Add |
| Late Bull | 0.60-0.80 | 60-80 | > 1.05 | Take profits |
| Distribution | > 0.80 | > 80 | LTH-SOPR spike | Reduce/Sell |

### Strategy 4: Ensemble Composite Signal

**Architecture**:
```
SMART MONEY (45%)  ----+
                       |
ON-CHAIN (30%)     ----+---> WEIGHTED COMBINER ---> FINAL SIGNAL
                       |
SENTIMENT (25%)    ----+
```

---

## 7. Research Findings

### Web Search Sources

1. **Copy Trading Diversification**
   - TradeFundrr: "For optimal diversification, copy between 3-5 traders"
   - Maximum 20-25% allocation per trader
   - Over-diversification dilutes returns

2. **Machine Learning in Trading**
   - FX24News: "ML allows assessment of decision quality regardless of market conditions"
   - Feature importance reveals predictive variables
   - Reinforcement learning for dynamic allocation

3. **Whale Tracking**
   - Nansen: Smart Money labels based on wallet behavior analysis
   - Whale movements provide early signals
   - Institutional positioning is key indicator

4. **Trading Metrics**
   - Sharpe, Sortino, Calmar ratios for risk-adjusted evaluation
   - Profit factor and win rate for strategy assessment
   - Max drawdown for risk tolerance

### Hyperliquid-Specific Insights

From Medium article on Hyperliquid whale analysis:
- Whale trading behavior shows patterns
- Simulation + ML combination effective
- Sample size matters for statistical significance

---

## 8. Recommendations

### Immediate (Week 1)

| Task | Priority | Effort |
|------|----------|--------|
| Enable `TraderWebSocketCollector` | Critical | 2 hours |
| Wire trader addresses to WS subscriptions | Critical | 2 hours |
| Connect `trader_positions` events to signal processor | Critical | 1 hour |

### Short-Term (Weeks 2-3)

| Task | Priority | Effort |
|------|----------|--------|
| Implement multi-dimensional weighting | High | 1 day |
| Build smart money signal processor | High | 1 day |
| Create whale alert system | High | 0.5 day |
| Add weight breakdown endpoints | Medium | 0.5 day |

### Medium-Term (Week 4)

| Task | Priority | Effort |
|------|----------|--------|
| Build feature importance analyzer | Medium | 1 day |
| Implement regime detection | Medium | 1 day |
| Create ML training pipeline | Low | 1 day |

### Long-Term (Week 5+)

| Task | Priority | Effort |
|------|----------|--------|
| Build ensemble signal combiner | Medium | 1 day |
| Add signal accuracy tracking | Medium | 0.5 day |
| Create ML retraining schedule | Low | 0.5 day |

---

## Key Success Metrics

1. **Signal Accuracy**: % of signals that predicted correct direction
2. **Alert Timeliness**: Seconds from whale action to alert
3. **Weight Effectiveness**: Higher-weighted traders performing better
4. **Regime Detection Accuracy**: How often regime classification was correct

---

## Conclusion

The key insight is that **no position inference is needed** - Hyperliquid provides actual position data. The `TraderWebSocketCollector` exists but is disabled. Enabling it unlocks the primary signal source.

For weighting:
- Use multi-dimensional approach (Performance + Size + Recency + Regime)
- Apply ML for discovery and regime detection
- Keep signal generation rule-based for interpretability

The recommended approach is a **hybrid system** where ML informs the rules, but rules generate the signals.
