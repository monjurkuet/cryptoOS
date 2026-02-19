# MongoDB Data Storage

This document provides a comprehensive overview of how data is stored in MongoDB, including collection schemas, indexing strategies, and retention policies.

## Overview

The market-scraper uses MongoDB as its primary persistent storage backend via the Motor async driver. Data models are optimized for:

- **Minimal storage size** - Short field names reduce document size
- **Time-series queries** - Timestamp-based indexing for efficient range queries
- **Automatic retention** - TTL indexes for data lifecycle management

## Connection

```python
from market_scraper.storage.mongo_repository import MongoRepository

# Connect to MongoDB
repo = MongoRepository(
    connection_string="mongodb://localhost:27017",
    database_name="cryptodata"
)
await repo.connect()
```

Configuration via environment:
```bash
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=cryptodata
```

---

## Collections

### Market Data Collections

#### `{symbol}_candles_{interval}` (e.g., `btc_candles_1m`)

OHLCV candle data from Hyperliquid WebSocket.

| Field | Type | Description |
|-------|------|-------------|
| `t` | datetime | Candle start timestamp (indexed) |
| `o` | float | Open price |
| `h` | float | High price |
| `l` | float | Low price |
| `c` | float | Close price |
| `v` | float | Volume |

**Example Document:**
```json
{
  "t": ISODate("2026-02-19T10:30:00Z"),
  "o": 96995.0,
  "h": 97010.0,
  "l": 96990.0,
  "c": 97005.0,
  "v": 15.5
}
```

**Note:** Only candles are collected. Individual trades and orderbook data are NOT stored, as they are not needed for signal generation. The system focuses on trader positions, not market microstructure.

---

### Trader Collections

#### `tracked_traders`

Currently tracked traders (upserted, not time-series).

| Field | Type | Description |
|-------|------|-------------|
| `eth` | str | Ethereum address (indexed, unique) |
| `name` | str | Display name (optional) |
| `score` | float | Current composite score (indexed) |
| `tags` | array | Automatic tags ["whale", "elite", etc.] |
| `active` | bool | Is being tracked (indexed) |
| `added_at` | datetime | When first added |
| `updated_at` | datetime | Last update time |

**Indexes:**
```javascript
{ "eth": 1 } (unique)
{ "score": -1 }
{ "active": 1 }
```

**Example Document:**
```json
{
  "eth": "0x1234567890abcdef...",
  "name": "WhaleTrader1",
  "score": 85.5,
  "tags": ["whale", "elite", "top_performer"],
  "active": true,
  "added_at": ISODate("2026-01-01T00:00:00Z"),
  "updated_at": ISODate("2026-02-19T10:30:00Z")
}
```

---

#### `trader_positions`

Time-series position snapshots for tracked traders.

| Field | Type | Description |
|-------|------|-------------|
| `eth` | str | Trader Ethereum address (indexed) |
| `t` | datetime | Timestamp (indexed, TTL) |
| `coin` | str | Trading symbol (indexed) |
| `sz` | float | Position size (+long, -short) |
| `ep` | float | Entry price |
| `mp` | float | Mark price |
| `upnl` | float | Unrealized PnL |
| `lev` | float | Leverage |
| `liq` | float | Liquidation price (optional) |

**Indexes:**
```javascript
{ "eth": 1, "coin": 1, "t": -1 }
{ "t": 1 } (TTL)
```

---

#### `trader_scores`

Time-series score history for trend analysis.

| Field | Type | Description |
|-------|------|-------------|
| `eth` | str | Trader Ethereum address (indexed) |
| `t` | datetime | Timestamp (indexed, TTL) |
| `score` | float | Composite score |
| `tags` | array | Tags at this time |
| `acct_val` | float | Account value |
| `all_roi` | float | All-time ROI |
| `month_roi` | float | Month ROI |
| `week_roi` | float | Week ROI |

---

#### `trader_current_state`

Current state including all open positions (denormalized for fast reads).

| Field | Type | Description |
|-------|------|-------------|
| `ethAddress` | str | Trader address |
| `positions` | array | Current open positions |
| `accountValue` | float | Total account value |
| `pnl` | float | Total PnL |

---

### Signal Collections

#### `signals`

Aggregated trading signals from tracked traders.

| Field | Type | Description |
|-------|------|-------------|
| `t` | datetime | Signal timestamp (indexed, TTL) |
| `symbol` | str | Trading symbol (indexed) |
| `rec` | str | Recommendation: BUY, SELL, NEUTRAL |
| `conf` | float | Confidence (0-1) |
| `long_bias` | float | Long bias (0-1) |
| `short_bias` | float | Short bias (0-1) |
| `net_exp` | float | Net exposure (-1 to 1) |
| `t_long` | int | Number of traders long |
| `t_short` | int | Number of traders short |
| `t_flat` | int | Number of traders flat |
| `price` | float | Price at signal time |

**Indexes:**
```javascript
{ "symbol": 1, "t": -1 }
{ "t": 1 } (TTL)
```

**Example Document:**
```json
{
  "t": ISODate("2026-02-19T10:30:00Z"),
  "symbol": "BTC",
  "rec": "BUY",
  "conf": 0.75,
  "long_bias": 0.7,
  "short_bias": 0.2,
  "net_exp": 0.5,
  "t_long": 45,
  "t_short": 15,
  "t_flat": 10,
  "price": 97000.0
}
```

---

#### `trader_signals`

Individual trader signals (position changes).

| Field | Type | Description |
|-------|------|-------------|
| `eth` | str | Trader address (indexed) |
| `t` | datetime | Signal timestamp (indexed, TTL) |
| `symbol` | str | Trading symbol (indexed) |
| `action` | str | Action: open, close, increase, decrease |
| `dir` | str | Direction: long, short |
| `sz` | float | Position size |
| `conf` | float | Signal confidence |
| `score` | float | Trader score at signal time |

---

### Leaderboard Collections

#### `leaderboard_history`

Historical snapshots of the Hyperliquid leaderboard.

| Field | Type | Description |
|-------|------|-------------|
| `t` | datetime | Snapshot timestamp (indexed, TTL) |
| `traders` | array | List of trader data |
| `count` | int | Number of traders in snapshot |

---

## Retention Policies

MongoDB TTL indexes automatically delete old documents. Retention is configurable in `config/traders_config.yaml`:

```yaml
storage:
  retention:
    leaderboard_history: 90   # Days
    trader_positions: 30
    trader_scores: 90
    signals: 30
    trader_signals: 30
    candles: 30
```

### How TTL Works

1. TTL indexes are created automatically on startup
2. MongoDB's TTL monitor runs every 60 seconds
3. Documents with timestamps older than `retention_days` are deleted
4. Changes to retention require index recreation

### Verify TTL Indexes

```bash
mongosh cryptodata --eval "
  db.trader_positions.getIndexes().forEach(i => {
    if (i.expireAfterSeconds)
      print(i.name, ':', i.expireAfterSeconds / 86400, 'days');
  });
"
```

---

## Indexes

### Query Performance Indexes

Created automatically by `MongoRepository._create_model_indexes()`:

```python
# Trader positions
{"eth": 1, "coin": 1, "t": -1}

# Trader scores
{"eth": 1, "t": -1}

# Tracked traders
{"eth": 1} (unique)
{"score": -1}
{"active": 1}

# Signals
{"symbol": 1, "t": -1}

# Trader signals
{"eth": 1, "t": -1}
{"symbol": 1, "t": -1}
```

---

## Storage Optimization

### Field Naming Convention

Short field names minimize document size:

| Short Name | Full Name | Savings |
|------------|-----------|---------|
| `t` | timestamp | 7 chars |
| `p` | price | 4 chars |
| `sz` | size | 1 char |
| `tid` | trade_id | 6 chars |
| `eth` | address | 4 chars |
| `rec` | recommendation | 11 chars |
| `conf` | confidence | 6 chars |

### Data Filtering

Data is filtered at the source to reduce storage:

- **Trades**: Only saves trades ≥ $1,000 USD
- **Orderbook**: Only saves when price changes ≥ 1%
- **Trader positions**: Event-driven saves (only on change)

### Bulk Operations

Use bulk methods for better performance:

```python
# Efficient bulk trade insert
await repo.store_trades_bulk(trades, symbol="BTC")

# Use upsert for idempotent operations
await repo.upsert_tracked_trader(trader)
```

---

## Query Examples

### Get Latest Signal

```python
signal = await repo.get_latest_signal(symbol="BTC")
```

### Get Trader Position History

```python
positions = await repo.get_trader_positions(
    address="0x...",
    symbol="BTC",
    limit=100,
    start=datetime.now() - timedelta(days=7)
)
```

### Get Tracked Traders by Score

```python
traders = await repo.get_tracked_traders(
    min_score=70,
    tag="whale",
    limit=50
)
```

### Get Signal Statistics

```python
stats = await repo.get_signal_stats(
    symbol="BTC",
    start_time=datetime.now() - timedelta(hours=24)
)
# Returns: {total, buy, sell, neutral, avg_confidence, avg_long_bias}
```

---

## MongoDB Compass Queries

Useful queries for data exploration:

```javascript
// Recent trades over $10k
db.btc_trades.find({ usd: { $gt: 10000 } }).sort({ t: -1 }).limit(100)

// Large buy orders
db.btc_trades.find({ side: "B", usd: { $gt: 50000 } }).sort({ t: -1 })

// Top 10 traders by score
db.tracked_traders.find({ active: true }).sort({ score: -1 }).limit(10)

// Whale traders
db.tracked_traders.find({ tags: "whale", active: true })

// Recent BUY signals
db.signals.find({ rec: "BUY" }).sort({ t: -1 }).limit(20)

// Collection sizes
db.btc_trades.stats()
db.trader_positions.stats()
```

---

## Backup & Recovery

### Export Collections

```bash
# Export specific collection
mongodump --db=cryptodata --collection=tracked_traders --out=backup/

# Export entire database
mongodump --db=cryptodata --out=backup/
```

### Import Collections

```bash
mongorestore --db=cryptodata backup/cryptodata/
```

---

## Monitoring

### Health Check

```python
health = await repo.health_check()
# Returns: {status, latency_ms, document_count, storage_size_mb}
```

### Collection Stats

```javascript
// Get collection statistics
db.btc_trades.stats()

// Index usage
db.btc_trades.aggregate([{ $indexStats: {} }])
```

---

*Last Updated: February 2026*
