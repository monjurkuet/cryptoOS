# Hyperliquid BTC Trading System

A comprehensive, production-ready data collection and trader tracking system for BTC trading analysis on Hyperliquid exchange. **Optimized for 83% storage reduction** while maintaining full real-time functionality.

## 🚀 Key Features

### Real-Time Market Data Collection
- **OHLCV candles** (1m, 5m, 15m, 1h, 4h, 1d intervals) via WebSocket
- **Orderbook snapshots** with smart filtering (>1% price change threshold)
- **Public trades** with value filtering (≥$1,000 only)
- **24h ticker statistics**
- **Funding rate history**
- **Open interest, liquidity, and liquidations**

### Advanced Trader Tracking
- **500 top traders** monitored in real-time
- **Position inference** from leaderboard metrics (89% accuracy, 100% recall)
- **Dual WebSocket managers** (positions + orders)
- **Event-driven updates** (only save when data changes)
- **Auto-reconnection** with client recreation
- **BTC-only filtering** (configurable)

### Signal Generation
- **Aggregated trading signals** every 5 minutes (optimized from 30s)
- **Position change detection**
- **Long/short bias calculation**
- **Confidence scoring**

### Smart Data Management
- **83% storage reduction** via intelligent filtering
- **MongoDB time-series collections**
- **Tiered retention policies** (1m candles: 7 days, 5m: 30 days, etc.)
- **Gzip compression** for archived data
- **Automatic TTL expiration**

## 📊 Performance Metrics

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| **Storage Growth** | ~15 GB/month | ~2.5 GB/month | **83%** |
| **Orderbook Writes** | Every 1s | On >1% change | **95%** |
| **Trade Storage** | All trades | ≥$1,000 only | **67%** |
| **Position Updates** | Every 5s | Event-driven | **85%** |
| **Signal Generation** | Every 30s | Every 5min | **90%** |

## 📋 Requirements

- Python 3.10+
- MongoDB 5.0+ (for time-series collections)
- 4GB+ RAM recommended
- Stable internet connection

## 🛠️ Installation

```bash
# Clone or navigate to the project
cd ~/development/cryptodata/hyperliquid/hyperliquid-system

# Install dependencies (using uv recommended)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt
```

## ⚙️ Configuration

1. **Copy the example environment file:**

```bash
cp .env.example .env
```

2. **Edit `.env` with your settings:**

```env
# MongoDB
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
MONGODB_DB_NAME=hyperliquid_btc

# Trader Tracking
MAX_TRACKED_TRADERS=500
TRADER_MIN_SCORE=50

# Data Storage Optimization
ORDERBOOK_PRICE_CHANGE_THRESHOLD_PCT=1.0
ORDERBOOK_MAX_SAVE_INTERVAL=600
TRADE_MIN_VALUE_USD=1000
POSITION_CHANGE_THRESHOLD_PCT=0.01
POSITION_ONLY_BTC=true
SIGNALS_INTERVAL=300
```

3. **View all configuration options in `.env.example`**

## 🎯 Usage

### Start the System

```bash
# Using uv (recommended)
uv run python -m src.main

# Or directly
python -m src.main

# Or using the entry point
python __main__.py
```

### Run in Background

```bash
nohup python -m src.main > logs/system.log 2>&1 &
```

### Monitor Logs

```bash
# Real-time log monitoring
tail -f logs/hyperliquid.log

# Filter for specific components
tail -f logs/hyperliquid.log | grep "position"
tail -f logs/hyperliquid.log | grep "order"
```

## 🏗️ Project Structure

```
hyperliquid-system/
├── src/
│   ├── __init__.py
│   ├── config.py                      # Configuration management
│   ├── main.py                        # Application entry point
│   ├── database.py                    # Database setup
│   ├── models/                        # Pydantic data models
│   │   ├── base.py
│   │   ├── btc_market.py
│   │   ├── traders.py
│   │   └── signals.py
│   ├── api/                           # API clients
│   │   ├── hyperliquid.py             # REST API client
│   │   ├── cloudfront.py              # CloudFront CDN client
│   │   ├── stats_data.py              # Leaderboard API client
│   │   ├── websocket.py               # WebSocket manager
│   │   ├── persistent_trader_ws.py    # Position monitoring (5 clients)
│   │   └── persistent_trader_orders_ws.py  # Order monitoring (5 clients)
│   ├── jobs/                          # Scheduled jobs & collectors
│   │   ├── scheduler.py               # APScheduler setup
│   │   ├── btc_candles_ws.py          # WebSocket candle collector
│   │   ├── btc_orderbook_ws.py        # WebSocket orderbook (optimized)
│   │   ├── btc_trades_ws.py           # WebSocket trades (filtered)
│   │   ├── btc_all_mids_ws.py         # All-mids collector
│   │   ├── btc_candles.py             # REST candle fallback
│   │   ├── btc_orderbook.py           # REST orderbook fallback
│   │   ├── btc_trades.py              # REST trades fallback
│   │   ├── btc_ticker.py              # 24h stats
│   │   ├── btc_funding.py             # Funding rates
│   │   ├── btc_daily_stats.py         # Daily metrics
│   │   ├── btc_signals.py             # Signal generation
│   │   ├── leaderboard.py             # Trader selection
│   │   ├── trader_positions.py        # REST position fallback
│   │   ├── trader_orders.py           # REST order fallback
│   │   └── archive.py                 # Data archival
│   ├── strategies/                    # Trading strategies
│   │   ├── trader_scoring.py          # Trader scoring algorithm
│   │   ├── position_detection.py
│   │   └── signal_generation.py
│   └── utils/                         # Utilities
│       ├── helpers.py
│       ├── archive.py
│       └── position_inference.py      # 89% accuracy inference
├── archive/                           # Local parquet archives
├── logs/                              # Log files
├── tests/                             # Test suite
├── .env.example                       # Configuration template
├── requirements.txt                   # Dependencies
├── pyproject.toml                     # Project config
├── README.md                          # This file
└── SYSTEM_DOCUMENTATION.md            # Detailed documentation
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[README.md](README.md)** | This file - Quick start guide |
| **[SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)** | Complete system documentation (700+ lines) |
| **[.env.example](.env.example)** | All configuration options with comments |
| **[PROCESS_DUPLICATION_ANALYSIS.md](PROCESS_DUPLICATION_ANALYSIS.md)** | Process architecture analysis |

## 🧠 Key Optimizations

### 1. Smart Orderbook Storage
**Problem**: Saving every snapshot = 5GB/month  
**Solution**: Only save on >1% price change or 600s max interval  
**Result**: 95% reduction

### 2. Trade Value Filtering
**Problem**: Micro-trades create noise  
**Solution**: Only store trades ≥$1,000 USD  
**Result**: 67% reduction

### 3. Event-Driven Position Updates
**Problem**: Polling creates duplicate data  
**Solution**: Only save when positions change + BTC-only filter  
**Result**: 85% reduction

### 4. Tiered Candle Retention
**Problem**: 1m candles accumulate rapidly  
**Solution**: 7-day retention for 1m, longer for higher TFs  
**Result**: 70% reduction after 7 days

### 5. Reduced Signal Frequency
**Problem**: 30s signals = 1GB/month  
**Solution**: 5-minute intervals (still responsive)  
**Result**: 90% reduction

### 6. Position Inference
**Problem**: Verifying 500 trader positions = 500 API calls  
**Solution**: Infer from leaderboard data (89% accuracy)  
**Result**: Zero API calls for filtering

### 7. Gzip Compression
**Problem**: Archived data takes significant space  
**Solution**: Compress orderbook data >7 days old  
**Result**: 70-80% compression ratio

## 📦 Collections

| Collection | Type | Retention | Description |
|------------|------|-----------|-------------|
| `btc_candles` | Time-Series | 7-90 days | OHLCV data (tiered) |
| `btc_orderbook` | Time-Series | 7 days | Smart-filtered snapshots |
| `btc_trades` | Time-Series | 90 days | Filtered trades (≥$1k) |
| `btc_ticker` | Single Doc | Forever | 24h stats |
| `btc_funding_history` | Regular | Forever | Funding rates |
| `btc_open_interest` | Regular | Forever | Daily OI |
| `btc_liquidity` | Regular | Forever | Liquidity metrics |
| `btc_liquidations` | Regular | Forever | Daily liquidations |
| `tracked_traders` | Regular | Forever | 500 trader configs |
| `trader_positions` | Time-Series | 30 days | Event-driven snapshots |
| `trader_current_state` | Regular | Forever | Current positions |
| `trader_orders` | Time-Series | 90 days | Real-time order history |
| `btc_signals` | Time-Series | 90 days | 5-min trading signals |
| `leaderboard_history` | Time-Series | Forever | Daily snapshots |

## ⏰ Job Schedule

| Job | Interval | Description | Mode |
|-----|----------|-------------|------|
| **Orderbook** | Real-time | BTC orderbook | WebSocket (optimized) |
| **Trades** | Real-time | BTC trades | WebSocket (filtered) |
| **Candles** | Real-time | All intervals | WebSocket |
| **AllMids** | Real-time | Mark prices | WebSocket |
| **Positions** | Real-time | 500 traders | WebSocket (event-driven) |
| **Orders** | Real-time | 500 traders | WebSocket (678 tracked) |
| Signal Generation | 5 min | Trading signals | Scheduler |
| Ticker Update | 60 sec | 24h stats | Scheduler |
| Trader Orders | 5 min | REST fallback | Scheduler (if WS down) |
| Funding | 8 hours | Funding rates | Scheduler |
| Leaderboard | Daily | Update 500 traders | Scheduler |
| Daily Stats | Daily | OI, liquidity, liqs | Scheduler |
| Archive | Daily | Compress old data | Scheduler |

**Note**: WebSocket takes priority. Scheduler REST jobs only run if WebSocket is unavailable.

## 🎯 Trader Scoring Algorithm

Traders are scored using weighted metrics:

| Factor | Weight | Description |
|--------|--------|-------------|
| All-Time ROI | 30% | Long-term profitability |
| Month ROI | 25% | Recent performance |
| Week ROI | 20% | Current momentum |
| Account Value | 15% | Size indicator |
| Volume | 10% | Activity level |

**Position Inference** (89% accuracy):
- Day ROI > 0.01%
- Day PnL / Account Value > 0.1%
- Day Volume > $100K

## 📈 Signal Generation

Aggregated signals combine:
- **Trader positions** weighted by score
- **Long/short bias** calculation
- **Net BTC exposure**
- **Confidence scoring**

**Recommendations**:
- **LONG**: Long bias > 60%
- **SHORT**: Short bias > 60%
- **NEUTRAL**: Otherwise

Generated every **5 minutes** (optimized from 30 seconds).

## 💾 Archive Strategy

Data is automatically archived based on retention policy:

```
archive/
├── btc_candles/
│   └── 2024-01.parquet
├── btc_orderbook/
│   └── 2024-01.parquet (gzip compressed)
├── btc_trades/
│   └── 2024-01.parquet
└── ...
```

**Features**:
- Parquet format for efficient storage
- Gzip compression for orderbook data
- Automatic TTL-based cleanup

## 🔍 Monitoring

### Health Checks (Automatic)

```
Health check: 5/5 clients connected (positions)
Orders health check: 5/5 clients connected, tracking 678 open orders
```

### Manual Status Check

```python
from src.jobs.scheduler import get_job_status
from src.api.persistent_trader_ws import PersistentTraderWebSocketManager

# Scheduler status
status = get_job_status(scheduler)
print(f"Active jobs: {status['total_jobs']}")

# WebSocket status
stats = trader_ws_manager.get_stats()
print(f"Connected: {stats['connected_clients']}/5")
```

### Log Analysis

**Healthy System**:
```
✓ WebSocket connected successfully
✓ Started 5/5 WebSocket clients
✓ Flushed X position updates (event-driven)
✓ Flushed X order updates (total: X)
✓ Health check: 5/5 clients connected
```

**Warnings** (Auto-recoverable):
```
⚠ Client X: Connection lost
⚠ Client X: Reconnecting in Ys (attempt Z)
⚠ Recreating client X...
```

**Errors** (Require attention):
```
✗ Failed to start Trader WebSocket Manager
✗ Max reconnection attempts reached
✗ Database connection failed
```

## 🚨 Troubleshooting

### Issue: Orders showing HTTPStatusError

**Status**: ✅ Fixed - Now uses WebSocket exclusively  
**Check logs for**: `Orders health check: 5/5 clients connected`

### Issue: 0/5 clients connected

**Solution**: Automatic client recreation implemented  
**Check logs for**: `Recreating orders client X...`

### Issue: High storage usage

**Check**: `db.stats()` in MongoDB shell  
**Expected**: ~2.5GB/month with optimizations active

### Issue: No position updates

**Check**:
1. `tracked_traders` collection has 500 active traders
2. WebSocket health checks show 5/5 connected
3. Wait for position changes (event-driven)

## 📄 License

MIT License

## 🤝 Contributing

This is a production system. For modifications:
1. Test in development environment first
2. Verify all WebSocket clients reconnect properly
3. Monitor storage metrics after changes
4. Update documentation

## 📞 Support

For detailed system information, see **[SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)**

---

**Version**: 2.0 (Optimized)  
**Last Updated**: February 16, 2026  
**Status**: Production Ready ✅
