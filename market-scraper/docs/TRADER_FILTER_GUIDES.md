# Trader Filter Configuration Guide

This guide provides detailed configurations for different trader focus strategies on the Hyperliquid leaderboard. Each profile is optimized for specific trading objectives and risk tolerances.

---

## Table of Contents

1. [Trader Classification Hierarchy](#trader-classification-hierarchy)
2. [Performance Metrics Explained](#performance-metrics-explained)
3. [Focus Profiles](#focus-profiles)
   - [Whale Focus](#1-whale-focus)
   - [Mega Whale (Humpback) Focus](#2-mega-whale-humpback-focus)
   - [Smart Money Focus](#3-smart-money-focus)
   - [Consistent Performers Focus](#4-consistent-performers-focus)
   - [High ROI Focus](#5-high-roi-focus)
   - [Active Traders Focus](#6-active-traders-focus)
   - [Balanced Focus](#7-balanced-focus)
   - [Conservative Focus](#8-conservative-focus)
4. [Custom Configuration](#custom-configuration)
5. [Terminology Reference](#terminology-reference)

---

## Trader Classification Hierarchy

The crypto community uses a **nautical-themed hierarchy** to classify traders based on their account value. This terminology originates from Bitcoin holder classifications but applies broadly to cryptocurrency trading.

### By Account Value (USD)

| Classification | Account Value | Market Influence | Typical Profile |
|----------------|---------------|------------------|-----------------|
| **Krill** | < $1,000 | Minimal | New traders, small retail |
| **Fish** | $1,000 - $10,000 | Low | Small retail traders |
| **Seal** | $10,000 - $100,000 | Low-Moderate | Regular investors |
| **Dolphin** | $100,000 - $500,000 | Moderate | Active traders, mid-tier |
| **Shark** | $500,000 - $1,000,000 | High | Significant traders |
| **Whale** | $1,000,000 - $10,000,000 | Very High | Major investors, institutions |
| **Mega Whale (Humpback)** | > $10,000,000 | Extreme | Large institutions, funds |

### Hyperliquid Leaderboard Minimum Criteria

Per Hyperliquid's official criteria:
- **Minimum Account Value**: $100,000 USDC
- **Minimum Trading Volume**: $10,000,000 USDC
- **ROI Calculation**: `ROI = PnL / max(100, starting_account_value + maximum_net_deposits)`

---

## Performance Metrics Explained

### ROI (Return on Investment)

| Metric | Description | Significance |
|--------|-------------|--------------|
| **Day ROI** | 24-hour return | Short-term performance, indicates active positions |
| **Week ROI** | 7-day return | Medium-term consistency |
| **Month ROI** | 30-day return | Sustained performance indicator |
| **All-Time ROI** | Lifetime return | Overall trader skill, long-term track record |

### ROI Thresholds (Industry Standards)

| ROI Level | Day | Week | Month | All-Time |
|-----------|-----|------|-------|----------|
| **Exceptional** | > 5% | > 20% | > 50% | > 200% |
| **Excellent** | > 2% | > 10% | > 30% | > 100% |
| **Good** | > 0.5% | > 5% | > 15% | > 50% |
| **Average** | > 0% | > 0% | > 0% | > 0% |
| **Poor** | < 0% | < 0% | < 0% | < 0% |

### Volume Classifications

| Level | Monthly Volume | Description |
|-------|---------------|-------------|
| **Ultra High** | > $100,000,000 | Market makers, institutional |
| **Very High** | $50,000,000 - $100,000,000 | Professional traders |
| **High** | $10,000,000 - $50,000,000 | Active professionals |
| **Medium** | $1,000,000 - $10,000,000 | Active retail |
| **Low** | < $1,000,000 | Casual traders |

---

## Focus Profiles

### 1. Whale Focus

**Objective**: Track only the largest traders with significant market influence. These traders can move markets with their positions and often have access to better information.

**Characteristics**:
- Account value ≥ $5,000,000
- High volume trading
- Institutional-grade strategies
- Lower frequency, higher impact trades

**Configuration**:
```yaml
# config/market_config.yaml - Whale Focus

scoring:
  weights:
    all_time_roi: 25
    month_roi: 20
    week_roi: 15
    account_value: 30  # Higher weight on account size
    volume: 10
  consistency_bonus: 5

filters:
  min_score: 40
  max_count: 100
  min_account_value: 5000000  # $5M minimum

account_value_tiers:
  - threshold: 50000000    # $50M+
    points: 20
  - threshold: 10000000    # $10M+
    points: 18
  - threshold: 5000000     # $5M+
    points: 15
  - threshold: 1000000     # $1M+
    points: 10
  - threshold: 0
    points: 0

tags:
  whale:
    threshold: 10000000    # $10M+ for whale tag
  large:
    threshold: 5000000     # $5M+ for large tag
  top_performer:
    min_score: 70
  elite:
    min_score: 85

storage:
  refresh_interval: 3600  # 1 hour
  keep_snapshots: true
```

**Use Case**: Best for traders who want to follow institutional money and catch large market moves early.

---

### 2. Mega Whale (Humpback) Focus

**Objective**: Track only the absolute largest accounts - institutions, funds, and legendary traders with $10M+ accounts.

**Characteristics**:
- Account value ≥ $10,000,000
- Extreme market influence
- Often institutional or fund managers
- Very selective, high-conviction trades

**Configuration**:
```yaml
# config/market_config.yaml - Mega Whale Focus

scoring:
  weights:
    all_time_roi: 30
    month_roi: 25
    week_roi: 15
    account_value: 20
    volume: 10
  consistency_bonus: 10

filters:
  min_score: 50
  max_count: 50
  min_account_value: 10000000  # $10M minimum

account_value_tiers:
  - threshold: 100000000    # $100M+
    points: 25
  - threshold: 50000000     # $50M+
    points: 22
  - threshold: 25000000     # $25M+
    points: 20
  - threshold: 10000000     # $10M+
    points: 18
  - threshold: 0
    points: 0

volume_tiers:
  - threshold: 500000000    # $500M+
    points: 15
  - threshold: 200000000    # $200M+
    points: 12
  - threshold: 100000000    # $100M+
    points: 10
  - threshold: 50000000     # $50M+
    points: 7
  - threshold: 0
    points: 0

tags:
  whale:
    threshold: 10000000
  top_performer:
    min_score: 60
  elite:
    min_score: 75
  high_volume:
    monthly_volume: 100000000

storage:
  refresh_interval: 3600
  keep_snapshots: true
```

**Use Case**: For experienced traders who want to track only the most significant market participants. Lower signal count but higher quality.

---

### 3. Smart Money Focus

**Objective**: Track traders with exceptional risk-adjusted returns who demonstrate skill rather than luck. Focuses on consistent profitability across all timeframes.

**Characteristics**:
- Positive ROI across day, week, month, and all-time
- Moderate to high account value
- Demonstrated skill through consistency
- Good risk management (no blow-ups)

**Configuration**:
```yaml
# config/market_config.yaml - Smart Money Focus

scoring:
  weights:
    all_time_roi: 30
    month_roi: 30
    week_roi: 20
    account_value: 10
    volume: 10
  consistency_bonus: 15  # Higher bonus for consistency

filters:
  min_score: 60
  max_count: 200
  min_account_value: 100000  # $100K minimum
  require_positive:
    all_time: true
    month: true
    week: true

account_value_tiers:
  - threshold: 5000000     # $5M+
    points: 15
  - threshold: 1000000     # $1M+
    points: 12
  - threshold: 500000      # $500K+
    points: 8
  - threshold: 100000      # $100K+
    points: 4
  - threshold: 0
    points: 0

tags:
  whale:
    threshold: 10000000
  large:
    threshold: 1000000
  top_performer:
    min_score: 75
  elite:
    min_score: 85
  consistent:
    require_positive:
      - day
      - week
      - month
      - allTime

storage:
  refresh_interval: 1800  # 30 minutes (more frequent updates)
  keep_snapshots: true
```

**Use Case**: Best for traders who want to identify skilled traders with proven track records, not just lucky ones.

---

### 4. Consistent Performers Focus

**Objective**: Track traders who show steady, reliable returns without extreme volatility. These traders often have disciplined strategies.

**Characteristics**:
- Positive returns in all timeframes
- Lower but steady ROI
- Good risk-adjusted performance
- Reliable signals

**Configuration**:
```yaml
# config/market_config.yaml - Consistent Performers

scoring:
  weights:
    all_time_roi: 25
    month_roi: 30  # Higher weight on recent consistency
    week_roi: 25
    account_value: 10
    volume: 10
  consistency_bonus: 20  # Maximum consistency bonus

filters:
  min_score: 55
  max_count: 150
  min_account_value: 50000  # $50K minimum
  require_positive:
    all_time: true
    month: true
    week: true

roi_multipliers:
  all_time: 25
  month: 40
  week: 60

tags:
  top_performer:
    min_score: 70
  consistent:
    require_positive:
      - day
      - week
      - month

storage:
  refresh_interval: 3600
  keep_snapshots: true
  keep_score_history: true  # Track score changes over time
```

**Use Case**: For risk-averse traders who prefer steady, reliable signals over high-risk high-reward plays.

---

### 5. High ROI Focus

**Objective**: Track the highest-performing traders regardless of account size. Focuses purely on returns.

**Characteristics**:
- Exceptional ROI numbers
- Can include smaller accounts with great performance
- Higher variance signals
- Potential alpha generation

**Configuration**:
```yaml
# config/market_config.yaml - High ROI Focus

scoring:
  weights:
    all_time_roi: 40  # Maximum weight on all-time performance
    month_roi: 30
    week_roi: 20
    account_value: 5
    volume: 5
  consistency_bonus: 5

roi_multipliers:
  all_time: 50
  month: 60
  week: 100

filters:
  min_score: 65
  max_count: 300
  min_account_value: 10000  # Low minimum - let ROI drive selection

account_value_tiers:
  - threshold: 1000000
    points: 10
  - threshold: 100000
    points: 5
  - threshold: 0
    points: 0

tags:
  high_performer:
    all_time_roi: 0.5  # 50%+ all-time ROI
  top_performer:
    min_score: 80
  elite:
    min_score: 90

storage:
  refresh_interval: 1800
  keep_snapshots: true
```

**Use Case**: For traders seeking alpha who are willing to accept higher variance for potentially higher returns.

---

### 6. Active Traders Focus

**Objective**: Track traders with high trading volume who are actively managing positions. These provide more frequent signals.

**Characteristics**:
- High monthly volume
- Frequent position changes
- Active day traders
- More signal frequency

**Configuration**:
```yaml
# config/market_config.yaml - Active Traders

scoring:
  weights:
    all_time_roi: 25
    month_roi: 25
    week_roi: 20
    account_value: 10
    volume: 20  # Higher weight on volume
  consistency_bonus: 5

filters:
  min_score: 50
  max_count: 250
  min_account_value: 25000

volume_tiers:
  - threshold: 500000000    # $500M+
    points: 20
  - threshold: 200000000    # $200M+
    points: 15
  - threshold: 100000000    # $100M+
    points: 12
  - threshold: 50000000     # $50M+
    points: 10
  - threshold: 20000000     # $20M+
    points: 7
  - threshold: 5000000      # $5M+
    points: 4
  - threshold: 0
    points: 0

tags:
  high_volume:
    monthly_volume: 100000000
  medium_volume:
    monthly_volume: 20000000

position_inference:
  enabled: true
  confidence_threshold: 0.3  # Lower threshold for more signals
  indicators:
    day_roi_threshold: 0.00005
    pnl_ratio_threshold: 0.0005
    day_volume_threshold: 50000

storage:
  refresh_interval: 1800  # 30 minutes
```

**Use Case**: For day traders who want frequent signals and active position updates.

---

### 7. Balanced Focus

**Objective**: A balanced approach that considers all factors equally. Good default configuration for most users.

**Characteristics**:
- Equal weight on all metrics
- Moderate account size filter
- Balanced ROI requirements
- Good mix of quality and quantity

**Configuration**:
```yaml
# config/market_config.yaml - Balanced Focus (Default)

scoring:
  weights:
    all_time_roi: 30
    month_roi: 25
    week_roi: 20
    account_value: 15
    volume: 10
  consistency_bonus: 5

roi_multipliers:
  all_time: 30
  month: 50
  week: 100

filters:
  min_score: 50
  max_count: 500
  min_account_value: 10000

account_value_tiers:
  - threshold: 10000000
    points: 15
  - threshold: 5000000
    points: 12
  - threshold: 1000000
    points: 8
  - threshold: 100000
    points: 4
  - threshold: 0
    points: 0

volume_tiers:
  - threshold: 100000000
    points: 10
  - threshold: 50000000
    points: 7
  - threshold: 10000000
    points: 4
  - threshold: 1000000
    points: 2
  - threshold: 0
    points: 0

tags:
  whale:
    threshold: 10000000
  large:
    threshold: 1000000
  top_performer:
    min_score: 80
  elite:
    min_score: 90
  consistent:
    require_positive:
      - day
      - week
      - month
  high_performer:
    all_time_roi: 1.0
  high_volume:
    monthly_volume: 100000000
  medium_volume:
    monthly_volume: 10000000

storage:
  refresh_interval: 3600
  keep_snapshots: true
  keep_score_history: false
  retention_days: 30
```

**Use Case**: Default configuration suitable for most traders. Good balance of signal quality and quantity.

---

### 8. Conservative Focus

**Objective**: Maximum quality filtering for risk-averse traders. Only the most proven traders are tracked.

**Characteristics**:
- High minimum score
- High account value requirement
- Must be positive in all timeframes
- Limited to top performers only

**Configuration**:
```yaml
# config/market_config.yaml - Conservative Focus

scoring:
  weights:
    all_time_roi: 35
    month_roi: 30
    week_roi: 20
    account_value: 10
    volume: 5
  consistency_bonus: 10

filters:
  min_score: 75        # High minimum
  max_count: 50        # Limited count
  min_account_value: 500000  # $500K minimum
  require_positive:
    all_time: true
    month: true
    week: true

account_value_tiers:
  - threshold: 25000000
    points: 20
  - threshold: 10000000
    points: 18
  - threshold: 5000000
    points: 15
  - threshold: 1000000
    points: 10
  - threshold: 500000
    points: 5
  - threshold: 0
    points: 0

tags:
  whale:
    threshold: 10000000
  large:
    threshold: 1000000
  top_performer:
    min_score: 85
  elite:
    min_score: 90
  consistent:
    require_positive:
      - day
      - week
      - month

position_inference:
  enabled: true
  confidence_threshold: 0.7  # Higher threshold

storage:
  refresh_interval: 7200  # 2 hours
  keep_snapshots: true
  keep_score_history: true
```

**Use Case**: For traders who prioritize quality over quantity and want only the most reliable signals.

---

## Custom Configuration

### Building Your Own Profile

Use this template to create custom configurations:

```yaml
# config/market_config.yaml - Custom

# Step 1: Define your scoring weights (should roughly sum to 100)
scoring:
  weights:
    all_time_roi: XX    # Importance of long-term performance
    month_roi: XX        # Importance of recent performance
    week_roi: XX         # Importance of short-term performance
    account_value: XX    # Importance of trader size
    volume: XX           # Importance of trading activity
  consistency_bonus: X   # Bonus for all-positive timeframes

# Step 2: Set your filters
filters:
  min_score: XX          # Minimum score to track (0-100+)
  max_count: XXX         # Maximum traders to track
  min_account_value: XX  # Minimum account value in USD

  # Optional: Require positive performance
  require_positive:
    all_time: true/false
    month: true/false
    week: true/false

  # Optional: Exclude specific addresses
  exclude:
    addresses:
      - "0x..."          # Addresses to exclude
    tags:
      - "tag_name"       # Tags to exclude

# Step 3: Define tag thresholds
tags:
  whale:
    threshold: 10000000
  large:
    threshold: 1000000
  top_performer:
    min_score: 80
  elite:
    min_score: 90

# Step 4: Storage settings
storage:
  refresh_interval: 3600
  keep_snapshots: true
  keep_score_history: false
  retention_days: 30
```

### Quick Reference by Goal

| Goal | min_score | max_count | min_account_value | Key Setting |
|------|-----------|-----------|-------------------|-------------|
| Follow whales | 40 | 100 | 5,000,000 | account_value: 30 |
| Smart money | 60 | 200 | 100,000 | require_positive: all |
| High returns | 65 | 300 | 10,000 | all_time_roi: 40 |
| Active signals | 50 | 250 | 25,000 | volume: 20 |
| Conservative | 75 | 50 | 500,000 | High thresholds |
| Balanced | 50 | 500 | 10,000 | Equal weights |

---

## Terminology Reference

### Trader Classifications

| Term | Definition | Origin |
|------|------------|--------|
| **Whale** | Large holder/trader with significant market influence | Traditional finance, popularized in crypto |
| **Humpback** | Extremely large whale ($10M+ or 5000+ BTC) | Bitcoin community extension |
| **Shark** | Large trader below whale status | Marine hierarchy |
| **Dolphin** | Medium-sized active trader | Marine hierarchy |
| **Fish** | Small retail trader | Marine hierarchy |
| **Krill** | Micro trader, minimal impact | Marine hierarchy |
| **Smart Money** | Institutional or skilled traders with superior information | Traditional finance |
| **Alpha** | Returns exceeding market benchmark | Finance terminology |

### Performance Metrics

| Term | Definition | Calculation |
|------|------------|-------------|
| **ROI** | Return on Investment | (Gain - Cost) / Cost |
| **PnL** | Profit and Loss | Realized + Unrealized gains |
| **Win Rate** | Percentage of profitable trades | Wins / Total Trades |
| **Sharpe Ratio** | Risk-adjusted return | (Return - Risk-Free Rate) / Std Dev |
| **Drawdown** | Peak-to-trough decline | (Peak - Trough) / Peak |

### Trading Terms

| Term | Definition |
|------|------------|
| **Long** | Position betting price will increase |
| **Short** | Position betting price will decrease |
| **Leverage** | Borrowed capital to amplify position size |
| **Liquidation** | Forced position closure due to insufficient margin |
| **Perpetual** | Futures contract with no expiration |
| **Funding Rate** | Periodic payment between longs and shorts |

### Signal Types

| Signal | Meaning | Action |
|--------|---------|--------|
| **BUY** | Bullish sentiment from tracked traders | Consider long positions |
| **SELL** | Bearish sentiment from tracked traders | Consider short positions or exit longs |
| **NEUTRAL** | Mixed or unclear sentiment | Wait for confirmation |

---

## Data Retention

MongoDB TTL indexes automatically clean up old data based on configurable retention periods. Configure retention in `config/market_config.yaml`:

```yaml
storage:
  retention:
    leaderboard_history: 90    # Leaderboard snapshots (days)
    trader_positions: 30       # Position snapshots
    trader_scores: 90          # Score history
    signals: 30                # Trading signals
    trader_signals: 30         # Per-trader signals
    mark_prices: 30            # Mark price data
    trades: 7                  # Raw trade data
    orderbook: 7               # Orderbook snapshots
    candles: 30                # OHLCV candles
```

### Retention Recommendations

| Data Type | Recommended Retention | Reasoning |
|-----------|----------------------|-----------|
| `leaderboard_history` | 90 days | Track leaderboard changes over quarters |
| `trader_positions` | 30 days | Sufficient for position tracking |
| `trader_scores` | 90 days | Enable trend analysis |
| `signals` | 30 days | Recent signals are most relevant |
| `trader_signals` | 30 days | Individual signal history |
| `trades` | 7 days | High volume, less historical value |
| `orderbook` | 7 days | Very high volume, current state matters |
| `candles` | 30 days | Useful for technical analysis |

### How TTL Works

1. TTL indexes are created automatically on startup
2. MongoDB's TTL monitor runs every 60 seconds
3. Documents with timestamps older than `retention_days` are deleted
4. Changes to retention require index recreation (drop and recreate)

### Verify TTL Indexes

```bash
# Check TTL indexes in MongoDB
mongosh cryptodata --eval "
  db.trader_positions.getIndexes().forEach(i => {
    if (i.expireAfterSeconds) print(i.name, ':', i.expireAfterSeconds / 86400, 'days');
  });
"
```

---

## Best Practices

### 1. Start Conservative
Begin with the **Conservative Focus** and gradually increase `max_count` as you become comfortable with the signals.

### 2. Combine Profiles
Use multiple configurations for different strategies:
- Whale Focus for major moves
- Active Traders for day trading signals

### 3. Monitor Score Changes
Enable `keep_score_history: true` to track how trader scores evolve over time.

### 4. Adjust for Market Conditions
- **Bull Market**: Increase volume weight, reduce consistency requirements
- **Bear Market**: Increase consistency requirements, focus on capital preservation
- **High Volatility**: Increase account value requirements, reduce max_count

### 5. Regular Review
Review your tracked traders weekly:
- Check if signals are profitable
- Adjust min_score if too many/few traders
- Exclude consistently wrong traders

---

## Troubleshooting

### Too Few Traders
- Lower `min_score`
- Lower `min_account_value`
- Disable `require_positive` filters

### Too Many Traders
- Increase `min_score`
- Increase `min_account_value`
- Reduce `max_count`
- Add `require_positive` filters

### Signals Not Working
- Check if traders are actually active (volume)
- Verify position inference is enabled
- Increase refresh_interval for more updates
- Review excluded addresses/tags

---

*Last Updated: February 2026*
*Version: 1.0*
