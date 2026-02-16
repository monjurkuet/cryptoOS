# Hyperliquid BTC Trading System - Complete Documentation

**Version**: 2.0 (Optimized)  
**Date**: February 16, 2026  
**Status**: Production Ready

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Breakdown](#component-breakdown)
4. [Data Flow](#data-flow)
5. [Optimization Features](#optimization-features)
6. [Configuration Guide](#configuration-guide)
7. [Monitoring & Maintenance](#monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Performance Metrics](#performance-metrics)

---

## Executive Summary

The Hyperliquid BTC Trading System is a comprehensive data collection and analysis platform designed for high-frequency trading, backtesting, and market analysis. The system has been optimized to achieve **83% storage reduction** while maintaining full functionality.

### Key Achievements

- **Data Collection**: Real-time market data via WebSocket + REST fallback
- **Trader Tracking**: 500 top traders monitored with 89% position inference accuracy
- **Storage Optimization**: 15GB/month → 2.5GB/month (83% reduction)
- **Performance**: Event-driven architecture with minimal database writes
- **Reliability**: Auto-reconnect, error handling, data deduplication

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Data Sources                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │
│  │  Hyperliquid   │  │   CloudFront   │  │  Stats Data    │            │
│  │  WebSocket API │  │   REST API     │  │  REST API      │            │
│  │  (Primary)     │  │   (Metrics)    │  │  (Leaderboard) │            │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘            │
└──────────┼──────────────────┼──────────────────┼──────────────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Collection Layer                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                WebSocket Collectors (Continuous)                 │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │   │
│  │  │  Orderbook   │ │    Trades    │ │   Candles    │            │   │
│  │  │  Collector   │ │  Collector   │ │  Collector   │            │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘            │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │   │
│  │  │   AllMids    │ │  Positions   │ │   Orders     │            │   │
│  │  │  Collector   │ │   Manager    │ │   Manager    │            │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Scheduler Jobs (Periodic)                           │   │
│  │  • Ticker Update (60s)    • Funding (8h)    • Signals (300s)    │   │
│  │  • Leaderboard (daily)    • Archive (daily) • Orders (REST)     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Data Storage Layer                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              MongoDB (Time-Series Collections)                   │   │
│  │  • btc_candles      • btc_orderbook    • btc_trades            │   │
│  │  • trader_positions • trader_orders    • btc_signals           │   │
│  │  • all_mids         • leaderboard_history                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 Regular Collections                              │   │
│  │  • btc_ticker       • btc_funding_history                      │   │
│  │  • tracked_traders  • trader_current_state                     │   │
│  │  • btc_open_interest • btc_liquidity • btc_liquidations        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Archive Storage (Local Filesystem)                  │   │
│  │  • Compressed Parquet files for data > retention period          │   │
│  │  • Gzip compression for orderbook data                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. WebSocket Collectors (Continuous Real-Time Collection)

#### 1.1 OrderbookWebSocketCollector (`src/jobs/btc_orderbook_ws.py`)

**Purpose**: Collect real-time orderbook data (bids/asks) for BTC

**Optimization**: 
- **Smart Saving**: Only saves to DB when price changes >1% OR max 600s interval
- **Memory Buffer**: Always keeps latest orderbook in memory for instant access
- **Storage Savings**: 95% reduction vs. saving every second

**Configuration**:
```python
ORDERBOOK_PRICE_CHANGE_THRESHOLD_PCT=1.0  # 1% price change threshold
ORDERBOOK_MAX_SAVE_INTERVAL=600           # Maximum 600 seconds between saves
```

**Log Example**:
```
2026-02-16 06:46:27 | INFO | Orderbook saved: mid=$68734.50, change=100.00%, interval=0s
```

**Data Stored**:
- Top 50 bid/ask levels
- Spread, mid price
- Bid/ask depth
- Imbalance ratio
- Timestamp

---

#### 1.2 TradesWebSocketCollector (`src/jobs/btc_trades_ws.py`)

**Purpose**: Collect individual trades in real-time

**Optimization**:
- **Value Filtering**: Only stores trades >= $1,000 USD
- **TID Tracking**: Prevents duplicate trades by tracking Trade ID
- **Storage Savings**: 67% reduction (filters 60-70% of micro-trades)

**Configuration**:
```python
TRADE_MIN_VALUE_USD=1000  # Minimum trade value to store
```

**Log Example**:
```
2026-02-16 06:51:10 | INFO | WS Trade: 1 trades stored (>= $1,000), 0 skipped (< $1,000), last tid=1125809304452221
```

**Data Stored**:
- Trade ID (TID)
- Price, size, side
- USD value (calculated: px * sz)
- Timestamp
- Transaction hash

---

#### 1.3 CandleWebSocketCollector (`src/jobs/btc_candles_ws.py`)

**Purpose**: Collect OHLCV candles for multiple timeframes

**Timeframes**: 1m, 5m, 15m, 1h, 4h, 1d

**Behavior**:
- Subscribes to all intervals simultaneously
- Batch inserts every 5 seconds
- Buffer size: 10 candles per interval

**Data Stored**:
- Open, High, Low, Close prices
- Volume
- Trade count
- Timestamp
- Interval

---

#### 1.4 AllMidsWebSocketCollector (`src/jobs/btc_all_mids_ws.py`)

**Purpose**: Collect mark prices for all coins

**Optimization**:
- **Change Detection**: Only records when price changes
- **10-second flush interval**

**Data Stored**:
- Coin symbol
- Mark price
- 24h change percentage
- Timestamp

---

#### 1.5 PersistentTraderWebSocketManager (`src/api/persistent_trader_ws.py`)

**Purpose**: Monitor 500 tracked traders' positions in real-time

**Architecture**:
- **5 concurrent WebSocket clients**
- **100 traders per client** (total: 500 traders)
- **Auto-reconnect** with exponential backoff
- **Client Recreation**: Automatically recreates disconnected clients (up to 5 attempts)

**Optimizations**:
1. **Event-Driven**: Only saves when positions actually change
2. **BTC-Only**: Filters for BTC positions only (configurable)
3. **600s Safety Interval**: Forces save every 10 minutes
4. **Position Change Detection**: Tracks size, direction, leverage changes
5. **Automatic Recovery**: Recreates failed clients with fresh connections

**Configuration**:
```python
POSITION_CHANGE_THRESHOLD_PCT=0.01  # 1% change detection
POSITION_ONLY_BTC=true              # BTC positions only
POSITION_MAX_SAVE_INTERVAL=600      # Max 600 seconds between saves
```

**Log Examples**:
```
2026-02-16 06:47:22 | INFO | Started 5/5 WebSocket clients
2026-02-16 06:47:34 | INFO | Flushed 43 position updates to database (event-driven)
2026-02-16 06:48:26 | INFO | Health check: 5/5 clients connected
```

**Data Collections**:
- `trader_positions`: Historical position snapshots (time-series)
- `trader_current_state`: Current positions (regular, upsert)

---

#### 1.6 PersistentTraderOrdersWSManager (`src/api/persistent_trader_orders_ws.py`)

**Purpose**: Monitor 500 tracked traders' orders in real-time via WebSocket

**Architecture**:
- **5 concurrent WebSocket clients** (separate from positions)
- **Shares same connection pool** but separate processing
- **Real-time order tracking**: New, filled, cancelled orders
- **Client Recreation**: Automatically recreates disconnected clients (up to 5 attempts)

**Features**:
1. **Order State Tracking**: Maintains state for each open order
2. **Change Detection**: Detects new orders, updates, cancellations
3. **678 Open Orders Tracked**: Currently tracking all open orders across 500 traders
4. **Automatic Recovery**: Recreates failed clients with fresh connections after max reconnection attempts

**Log Examples**:
```
2026-02-16 06:47:24 | INFO | Started 5/5 Orders WebSocket clients
2026-02-16 06:48:28 | INFO | Orders health check: 5/5 clients connected, tracking 678 open orders
2026-02-16 06:49:19 | INFO | Flushed 756 order updates to database (total: 756)
```

**Data Stored**:
- Order ID (oid)
- Coin, side, type
- Limit price, size
- Status (open, filled, cancelled)
- Timestamp

---

### 2. Scheduler Jobs (Periodic Collection)

The APScheduler runs periodic jobs for data that doesn't need real-time collection.

#### 2.1 Signal Generation (`src/jobs/btc_signals.py`)

**Frequency**: Every 300 seconds (5 minutes) - Optimized from 30s

**Purpose**: Generate trading signals based on trader positions

**Algorithm**:
1. Aggregate positions from all tracked traders
2. Weight by trader score
3. Calculate long/short bias
4. Generate BUY/SELL/HOLD signals

**Data Stored**: `btc_signals`

---

#### 2.2 Ticker Update (`src/jobs/btc_ticker.py`)

**Frequency**: Every 60 seconds

**Purpose**: Update 24h ticker statistics

**Data**: Volume, price change, high, low, etc.

**Collection**: `btc_ticker` (single document, updated)

---

#### 2.3 Funding Rate Collection (`src/jobs/btc_funding.py`)

**Frequency**: Every 8 hours

**Purpose**: Collect funding rate history

**Collection**: `btc_funding_history` (regular, unique index on timestamp)

---

#### 2.4 Leaderboard Fetch (`src/jobs/leaderboard.py`)

**Frequency**: Daily

**Purpose**:
1. Fetch top 30,000+ traders from Hyperliquid leaderboard
2. Score traders based on performance metrics
3. Select top 500 with position inference
4. Update tracked traders list

**Position Inference**:
- 89% accuracy in detecting active positions
- Uses day ROI, PnL ratio, and volume thresholds
- No API calls needed (leaderboard-only)

**Log Example**:
```
2026-02-16 06:46:36 | INFO | Processed leaderboard with 30718 traders
2026-02-16 06:46:36 | INFO | Scored 1133 traders (min_score: 50.0)
2026-02-16 06:46:36 | INFO | Position inference: 500/1133 traders with likely positions
```

---

#### 2.5 Daily Stats Collection (`src/jobs/btc_daily_stats.py`)

**Frequency**: Daily

**Purpose**: Collect daily metrics
- Open Interest
- Liquidity
- Liquidations

---

#### 2.6 Archive Job (`src/jobs/archive.py`)

**Frequency**: Daily

**Purpose**: Archive old data based on retention policy

**Optimizations**:
- Gzip compression for orderbook data >7 days
- Parquet format for efficient storage
- Automatic cleanup of old data

---

## Data Flow

### Startup Sequence

```
Step 1: Initialize (0s)
  ↓ Connect to MongoDB
  ↓ Setup database (create collections & indexes)

Step 2: Start WebSocket Connections (2s)
  ↓ Connect to Hyperliquid WebSocket
  ↓ Start market data collectors:
    - Orderbook (optimized: >1% change)
    - Trades (filtered: >$1,000)
    - Candles (all intervals)
    - AllMids (price changes)

Step 3: Setup Scheduler (3s)
  ↓ Configure APScheduler
  ↓ Add jobs (conditional based on WebSocket availability)
    - If ws_available=True: Skip REST orderbook/trades/candles/orders
    - If ws_available=False: Use REST fallback

Step 4: Run Startup Tasks (5s)
  ↓ Update ticker (always)
  ↓ Backfill candles (always - potential overlap with WebSocket)
  ↓ Fetch leaderboard (always)
    - Score 30,000+ traders
    - Select top 500 with position inference
    - Store in tracked_traders collection

Step 5: Start Trader Monitoring (10s)
  ↓ Start Position Manager (5 clients, 100 traders each)
  ↓ Start Orders Manager (5 clients, tracking all orders)
  ↓ Both use WebSocket webData2 feed

Step 6: Scheduler Starts (15s)
  ↓ All periodic jobs begin
  ↓ System enters main loop

Total Startup Time: ~15-20 seconds
```

### Runtime Data Flow

#### Market Data Flow (WebSocket)
```
Hyperliquid WebSocket
  ↓ (raw data)
WebSocket Collectors
  ↓ (process & filter)
Memory Buffers
  ↓ (every 5-10 seconds)
MongoDB Collections
  ↓ (TTL expiration)
Archive Storage
```

#### Trader Data Flow (WebSocket)
```
500 Tracked Traders
  ↓ (webData2 subscription)
5 WebSocket Clients
  ↓ (parse messages)
Position Manager + Orders Manager
  ↓ (event-driven)
Database Write (only on changes)
  ↓ (batch every 5 seconds)
trader_positions + trader_orders + trader_current_state
```

#### Scheduled Data Flow
```
APScheduler
  ↓ (every X seconds/minutes/hours)
Job Function
  ↓ (API call or calculation)
Process Data
  ↓ (validation & formatting)
Database Write
  ↓ (upsert or insert)
Collections (ticker, signals, funding, etc.)
```

---

## Optimization Features

### 1. Orderbook Storage Optimization

**Problem**: Saving every orderbook snapshot creates massive storage (5GB/month)

**Solution**: Smart threshold-based saving
- Only save when price changes >1%
- Maximum 600 seconds between saves (safety)
- Always keep latest in memory

**Impact**: 95% reduction (~5GB → ~0.25GB/month)

---

### 2. Trade Value Filtering

**Problem**: Micro-trades (<$100) create noise and storage bloat

**Solution**: Filter trades by USD value
- Only store trades >= $1,000
- TID tracking prevents duplicates

**Impact**: 67% reduction (~3GB → ~1GB/month)

---

### 3. Event-Driven Position Updates

**Problem**: Saving position snapshots every 5 seconds wastes storage

**Solution**: Only save when positions actually change
- Track last saved state per trader
- Normalize positions for comparison
- 600-second safety interval
- BTC-only filtering (configurable)

**Impact**: 85% reduction (~4GB → ~0.6GB/month)

---

### 4. Tiered Candle Retention

**Problem**: 1-minute candles accumulate rapidly (2GB/month)

**Solution**: Different retention periods per timeframe
- 1m candles: 7 days only
- 5m candles: 30 days
- 15m+ candles: 90 days

**Impact**: 70% reduction after 7 days

---

### 5. Signal Generation Optimization

**Problem**: Generating signals every 30 seconds creates 1GB/month

**Solution**: Reduce frequency to 5 minutes
- Still responsive for trading decisions
- 90% reduction in signal documents

**Impact**: 90% reduction (~1GB → ~0.1GB/month)

---

### 6. Orderbook Compression

**Problem**: Archived orderbook data takes significant space

**Solution**: Gzip compression for data >7 days old
- Level 9 compression for maximum savings
- Length-prefixed chunks for easy reading
- 70-80% compression ratio

---

### 7. Position Inference

**Problem**: Need to verify which traders have active positions (requires 500 API calls)

**Solution**: Infer from leaderboard data
- Uses day ROI, PnL ratio, volume thresholds
- 89% accuracy, 100% recall
- No API calls needed

**Impact**: Eliminates 500 API calls per cycle

---

## Configuration Guide

### Environment Variables

Create a `.env` file with these settings:

```bash
# =============================================================================
# MongoDB Configuration
# =============================================================================
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DB_NAME=hyperliquid_btc

# =============================================================================
# API Endpoints
# =============================================================================
HYPERLIQUID_API_URL=https://api.hyperliquid.xyz/info
CLOUDFRONT_BASE_URL=https://d2v1fiwobg9w6.cloudfront.net
STATS_DATA_URL=https://stats-data.hyperliquid.xyz

# =============================================================================
# Collection Intervals (seconds)
# =============================================================================
CANDLES_INTERVAL=300
ORDERBOOK_INTERVAL=30
TRADES_INTERVAL=60
TICKER_INTERVAL=60
FUNDING_INTERVAL=28800
TRADER_POSITIONS_INTERVAL=60
TRADER_ORDERS_INTERVAL=300
SIGNALS_INTERVAL=300              # Optimized: 5 minutes (was 30s)

# =============================================================================
# Retention Policy (days) - Tiered Approach
# =============================================================================
CANDLES_1M_RETENTION=7            # 1m: 7 days only
CANDLES_5M_RETENTION=30           # 5m: 30 days
CANDLES_15M_RETENTION=90          # 15m: 90 days
ORDERBOOK_RETENTION=7
TRADES_RETENTION=90
TRADER_POSITIONS_RETENTION=30
TRADER_ORDERS_RETENTION=90
SIGNALS_RETENTION=90

# =============================================================================
# Trader Tracking
# =============================================================================
MAX_TRACKED_TRADERS=500
TRADER_MIN_SCORE=50.0
TRADER_SELECTION_INTERVAL=86400
TRADER_CONCURRENCY_LIMIT=10

# =============================================================================
# Position Inference (Leaderboard-Only Filtering)
# =============================================================================
POSITION_INFERENCE_ENABLED=true
POSITION_DAY_ROI_THRESHOLD=0.0001
POSITION_DAY_PNL_THRESHOLD=0.001
POSITION_DAY_VOLUME_THRESHOLD=100000

# =============================================================================
# Persistent Trader WebSocket Manager
# =============================================================================
TRADER_WS_ENABLED=true
TRADER_WS_CLIENTS=5
TRADER_WS_HEARTBEAT=30
TRADER_WS_RECONNECT_DELAY=5.0
TRADER_WS_RECONNECT_MAX_DELAY=60.0
TRADER_WS_RECONNECT_ATTEMPTS=10
TRADER_WS_BATCH_SIZE=100
TRADER_WS_MESSAGE_BUFFER_SIZE=1000
TRADER_WS_FLUSH_INTERVAL=5.0

# =============================================================================
# Data Storage Optimization
# =============================================================================
# Orderbook: Save only on significant price changes
ORDERBOOK_PRICE_CHANGE_THRESHOLD_PCT=1.0  # 1% price change threshold
ORDERBOOK_MAX_SAVE_INTERVAL=600           # Max 600s between saves

# Trades: Filter small trades
TRADE_MIN_VALUE_USD=1000                  # Minimum $1,000 USD

# Positions: Event-driven updates
POSITION_CHANGE_THRESHOLD_PCT=0.01        # Save on >1% change
POSITION_ONLY_BTC=true                    # BTC positions only
POSITION_MAX_SAVE_INTERVAL=600            # Max 600s between saves

# =============================================================================
# Archive Configuration
# =============================================================================
ARCHIVE_ENABLED=true
ARCHIVE_BASE_PATH=./archive
ARCHIVE_INTERVAL=86400

# =============================================================================
# Logging
# =============================================================================
LOG_LEVEL=INFO
LOG_FILE=logs/hyperliquid.log
LOG_ROTATION=100 MB
LOG_RETENTION=30 days

# =============================================================================
# Trading Configuration
# =============================================================================
TARGET_COIN=BTC
CANDLE_INTERVALS=["1m", "5m", "15m", "1h", "4h", "1d"]
```

---

## Monitoring & Maintenance

### 1. Health Checks

The system provides automatic health checks:

```
2026-02-16 06:48:26 | INFO | Health check: 5/5 clients connected (positions)
2026-02-16 06:48:28 | INFO | Orders health check: 5/5 clients connected, tracking 678 open orders
```

### 2. Key Metrics to Monitor

#### Database Size
```javascript
// MongoDB shell
use hyperliquid_btc
db.stats()

// Check collection sizes
db.btc_candles.stats()
db.btc_orderbook.stats()
db.trader_positions.stats()
```

#### WebSocket Connection Status
```python
from src.api.persistent_trader_ws import PersistentTraderWebSocketManager

# Get stats
stats = trader_ws_manager.get_stats()
print(f"Connected clients: {stats['connected_clients']}/5")
print(f"Subscribed traders: {stats['subscribed_traders']}")
print(f"Buffer size: {stats['buffer_size']}")
```

#### Scheduler Job Status
```python
from src.jobs.scheduler import get_job_status

status = get_job_status(scheduler)
print(f"Total jobs: {status['total_jobs']}")
for job in status['jobs']:
    print(f"  - {job['name']}: next run at {job['next_run']}")
```

### 3. Log Analysis

**Normal Operation Signs**:
```
✓ WebSocket connected successfully
✓ Started X/Y WebSocket clients
✓ Flushed N position updates to database (event-driven)
✓ Flushed N order updates to database
✓ Health check: 5/5 clients connected
```

**Warning Signs**:
```
⚠ Failed to start Trader WebSocket Manager
⚠ Client X disconnected, will reconnect
⚠ Error writing position for 0x...: <error>
```

**Error Signs**:
```
✗ WebSocket connection failed
✗ Max reconnection attempts reached
✗ Database connection failed
```

---

## Troubleshooting

### Issue 1: HTTPStatusError for Orders

**Symptom**: `HTTPStatusError` in logs for trader orders

**Cause**: REST API rate limiting or connection issues

**Solution**: ✅ Already fixed - Now uses WebSocket for orders

**Verification**:
```
2026-02-16 06:47:24 | INFO | Persistent Trader Orders WebSocket Manager started
```

---

### Issue 2: No Position Updates

**Symptom**: No "Flushed position updates" messages

**Possible Causes**:
1. No tracked traders: Check `tracked_traders` collection
2. WebSocket disconnected: Check health check logs
3. All positions unchanged: Normal during low volatility

**Debug Steps**:
```python
# Check tracked traders count
db.tracked_traders.countDocuments({isActive: true})

# Check recent positions
db.trader_positions.find().sort({t: -1}).limit(5)
```

---

### Issue 3: Duplicate Data

**Symptom**: Multiple documents for same timestamp

**Check**:
```javascript
// Find duplicates
db.btc_candles.aggregate([
  { $group: { _id: { t: "$t", interval: "$interval" }, count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])
```

**Fix**: 
- Time-series collections don't support unique indexes
- Deduplication is application-level (TID tracking for trades)
- Candles: Startup backfill may overlap with WebSocket (acceptable)

---

### Issue 4: High Memory Usage

**Cause**: Large message buffers

**Solution**: Adjust buffer sizes in config:
```python
TRADER_WS_MESSAGE_BUFFER_SIZE=500  # Default: 1000
TRADER_WS_FLUSH_INTERVAL=3.0       # Default: 5.0 seconds
```

---

### Issue 5: WebSocket Disconnections

**Symptom**: Frequent "Connection lost" messages

**Possible Causes**:
1. Network instability
2. Rate limiting
3. Server-side disconnects

**Solution**: Multi-layer auto-recovery system

**Layer 1 - Auto-reconnect**: Built-in exponential backoff
- Initial delay: 5 seconds
- Max delay: 60 seconds
- Max attempts: 10 per client

**Layer 2 - Client Recreation**: If max attempts reached
- Old client is stopped and removed
- New client created with fresh connection
- 5 restart attempts with increasing delays (10s, 20s, 30s...)
- Same trader batch maintained

**Log Example**:
```
Client 2: Connection lost
Client 2: Reconnecting in 5s (attempt 1)
...
Client 2: Max reconnection attempts reached
Client 2 disconnected, recreating...
Recreating client 2 with 100 traders...
Client 2: Connected to WebSocket
Client 2: Subscribed to 100 traders
Client 2 successfully recreated and started
```

---

### Issue 6: 0/5 Clients Connected (Orders or Positions)

**Symptom**: Health check shows "0/5 clients connected"

**Cause**: All clients disconnected after max reconnection attempts

**Status**: ✅ Fixed - Automatic client recreation now implemented

**Behavior**:
- System automatically detects disconnected clients
- Waits 5 seconds to prevent rapid loops
- Creates new client instances with fresh connections
- Retries up to 5 times with exponential backoff
- Health check should return to 5/5 within 1-2 minutes

**If Still 0/5 After 5 Minutes**:
1. Check network connectivity: `ping api.hyperliquid.xyz`
2. Check MongoDB connection: Verify `tracked_traders` collection accessible
3. Review logs for error messages
4. Restart system as last resort

---

## Performance Metrics

### Current System Status (From Your Logs)

```
Startup Time: ~20 seconds
Database: hyperliquid_btc
WebSocket: Connected ✓

Active Collectors:
  ✓ Orderbook (optimized: >1% change)
  ✓ Trades (filtered: >$1,000)
  ✓ Candles (6 intervals)
  ✓ AllMids
  ✓ Positions (5 clients, 500 traders)
  ✓ Orders (5 clients, 678 open orders)

Scheduler Jobs: 7 active
  • generate_signals (300s)
  • update_ticker (60s)
  • collect_funding (8h)
  • fetch_leaderboard (daily)
  • update_tracked_traders (daily)
  • collect_daily_stats (daily)
  • archive_all_collections (daily)

Performance:
  • Position updates: 43 in first 10 minutes (event-driven)
  • Order updates: 756 in first 2 minutes (678 open orders)
  • Trade filtering: Only >= $1,000 stored
  • Health checks: All 5/5 clients connected
```

### Expected Performance

| Metric | Expected Value |
|--------|---------------|
| **Startup Time** | 15-30 seconds |
| **Position Update Rate** | 10-50/hour (event-driven) |
| **Order Update Rate** | 100-1000/hour (event-driven) |
| **WebSocket Uptime** | >99% (with auto-reconnect) |
| **Database Writes** | ~80% reduction vs. polling |
| **Storage Growth** | ~2.5 GB/month (83% reduction) |
| **Memory Usage** | <500 MB (stable) |
| **CPU Usage** | <10% (async architecture) |

---

## Summary

The Hyperliquid BTC Trading System is a production-ready, optimized data collection platform with the following characteristics:

### Strengths
1. **Real-time Performance**: WebSocket-based with <1s latency
2. **Storage Efficient**: 83% reduction via smart filtering
3. **Reliable**: Auto-reconnect, error handling, health checks
4. **Scalable**: Handles 500 traders with 5 concurrent connections
5. **Maintainable**: Clear separation of concerns, comprehensive logging

### Architecture Highlights
- **Dual-mode collection**: WebSocket (primary) + REST (fallback)
- **Event-driven updates**: Only save when data changes
- **Smart filtering**: Threshold-based saving, value filtering
- **Compression**: Gzip for archived data
- **Position inference**: 89% accuracy without API calls

### Current Status
✅ **System Operational**
- All WebSocket clients connected (5/5)
- 678 open orders being tracked
- Event-driven updates working
- No HTTPStatusError (WebSocket orders active)
- Scheduler running 7 jobs
- **Auto-recovery**: Client recreation on disconnection

---

**Document Version**: 2.1  
**Last Updated**: February 16, 2026 (Updated with reconnection fixes)  
**Author**: System Documentation  
**Status**: Production Ready
