# cryptoOS API & WebSocket Reference

**Purpose**: Complete reference of all working endpoints and WebSocket connections for fresh-start development.

---

## 1. REST API Endpoints (port 3845)

### Base URL
```
http://localhost:3845
```

### Health & Status
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/live` | GET | Liveness probe (thread-based, port 3846) — always responds |
| `/health/ready` | GET | Readiness probe — checks MongoDB, Redis, startup complete |
| `/health/startup` | GET | Startup status — in_progress / failed / ready |
| `/health/status` | GET | Detailed component health (cached 5s) |

### Market Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/markets` | GET | List available market symbols |
| `/api/v1/markets/{symbol}` | GET | Current market data for symbol |
| `/api/v1/markets/{symbol}/history` | GET | OHLCV candles — params: `timeframe` (1m,5m,15m,1h,4h,1d), `start_time`, `end_time`, `limit` (1-10000) |

### Traders
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/traders` | GET | List tracked traders with extensive filters — params: `limit` (1-500), `min_score`, `tag`, `has_positions`, `has_open_orders`, `position_status`, `updated_within_hours`, `address_contains`, `display_name_contains`, `max_score`, `account_value_min/max`, `tags_any/all/exclude`, `roi_*_min/max`, `volume_*_min/max`, `profitable_windows` (day,week,month,all_time), `sort_by` (score,account_value,last_position_update,address), `sort_dir` (asc/desc), `offset`, `include_total` (bool), `include_metrics` (bool), `addresses` (comma-separated) |
| `/api/v1/traders/{address}` | GET | Single trader detail with positions, open orders |
| `/api/v1/traders/batch` | POST | Batch query — body: `{addresses: string[], include_inactive: bool}` |

### Signals
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/signals` | GET | Historical signals — params: `hours` (1-168), `limit` (1-500), `recommendation` (BUY/SELL/NEUTRAL) |
| `/api/v1/signals/current` | GET | Current aggregated signal |
| `/api/v1/signals/latest` | GET | Alias for /current |
| `/api/v1/signals/stats` | GET | Signal statistics — params: `hours` (1-168) |
| `/api/v1/signals/{signal_id}` | GET | Single signal by ObjectId |

### Leaderboard (Raw — 39K traders)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/leaderboard/query` | GET | Query cached leaderboard snapshot — params: `limit` (1-500), `offset`, `sort_by` (accountValue, roi_all_time, roi_month, roi_week, roi_day, volume_month, pnl_all_time), `sort_desc`, `min/max_acct_val`, `min/max_roi_*`, `min/max_volume_month`, `min/max_pnl_all_time`, `has_positive` (comma: allTime,month,week,day), `addresses` (comma), `fetch_time` (ISO) |
| `/api/v1/leaderboard/tiers` | GET | Tier distribution of tracked traders |
| `/api/v1/leaderboard/run-promotions` | POST | Manually trigger promotion/demotion evaluation |

### On-Chain Metrics
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/onchain/btc/summary` | GET | Unified BTC on-chain metrics (all sources aggregated) |
| `/api/v1/onchain/btc/network` | GET | Blockchain.info: hash_rate_ghs, difficulty, block_height, total_btc, price_usd, market_cap_usd |
| `/api/v1/onchain/btc/sentiment` | GET | Fear & Greed + CBBI confidence |
| `/api/v1/onchain/btc/valuation` | GET | CBBI components: PiCycle, RUPL, RHODL, Puell, 2YMA, MVRV, ReserveRisk, Woobull, Trolololo |
| `/api/v1/onchain/btc/activity` | GET | Coin Metrics: active addresses, tx count, supply, market cap |
| `/api/v1/onchain/btc/sopr` | GET | SOPR, STH-SOPR, LTH-SOPR from Bitview |
| `/api/v1/onchain/btc/exchange-flows` | GET | Exchange flows: flow_in, flow_out, netflow, supply, 7d/30d averages |

### CBBI (Bitcoin Bull Run Index)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cbbi` | GET | Current CBBI confidence (0-100) + components |
| `/api/v1/cbbi/components` | GET | All 9 components with descriptions + historical |
| `/api/v1/cbbi/components/{name}` | GET | Single component detail |
| `/api/v1/cbbi/health` | GET | Connector health |

### Binance Account (saved read-only API keys)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/binance/accounts` | GET | List saved accounts |
| `/api/v1/binance/accounts` | POST | Save encrypted API keys |
| `/api/v1/binance/accounts/{id}` | DELETE | Delete account |
| `/api/v1/binance/positions/{id}` | GET | Positions for saved account |

### Auth
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register local account |
| `/api/v1/auth/login` | POST | Login (sets session cookie) |
| `/api/v1/auth/me` | GET | Current user |
| `/api/v1/auth/logout` | POST | Logout |

### Account Page (SSR)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/account` | GET | HTML dashboard page |

---

## 2. WebSocket Streaming (port 3845, path `/ws`)

### Connection
```
ws://localhost:3845/ws
```

### Protocol
**Client → Server:**
```json
{"action": "subscribe", "symbols": ["BTC"], "event_types": ["trader_positions", "ohlcv", "signals"]}
{"action": "unsubscribe", "symbols": ["BTC"], "event_type": "ohlcv"}
{"action": "ping"}
```

**Server → Client:**
```json
{"type": "ack", "action": "subscribed", "data": {"symbols": ["BTC"], "event_types": [...]}}
{"type": "event", "data": {StandardEvent JSON}}
{"type": "error", "error": "..."}
{"type": "pong"}
```

### Event Types Available
- `trader_positions` — Real-time position updates for tracked traders
- `ohlcv` — OHLCV candles (1m, 5m, 15m, 1h, 4h, 1d)
- `signals` — Generated BUY/SELL/NEUTRAL signals
- `leaderboard` — Periodic leaderboard snapshots
- `mark_price` — Mark price updates
- `trading_signal` — Raw signal events
- `coin_metrics`, `fear_greed_index`, `cbbi_index`, etc. — On-chain metrics

---

## 3. Hyperliquid API Endpoints (External — Working)

### REST
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `https://api.hyperliquid.xyz/info` | POST | Universal query endpoint (clearinghouseState, openOrders, meta, metaAndAssetCtxs, allMids, userFunding, etc.) |
| `https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` | GET | Full 39K trader leaderboard (GET, not POST) |

### WebSocket
| URL | Purpose |
|-----|---------|
| `wss://api.hyperliquid.xyz/ws` | Market data (candles, l2Book, trades, allMids, etc.) + webData2 for trader positions |

#### WebSocket Subscriptions
```json
// Candles (6 intervals per symbol)
{"method": "subscribe", "subscription": {"type": "candle", "coin": "BTC", "interval": "1m"}}
// Valid intervals: 1m, 5m, 15m, 1h, 4h, 1d

// Trader positions (webData2) — max 10 users per connection
{"method": "subscribe", "subscription": {"type": "webData2", "user": "0x..."}}

// All mids
{"method": "subscribe", "subscription": {"type": "allMids"}}

// Orderbook
{"method": "subscribe", "subscription": {"type": "l2Book", "coin": "BTC"}}
```

#### webData2 Response Format
```json
{
  "channel": "webData2",
  "data": {
    "user": "0x...",
    "clearinghouseState": {
      "assetPositions": [
        {"position": {"coin": "BTC", "szi": "1.5", "entryPx": "50000", "markPx": "51000", "unrealizedPnl": "1500", "leverage": {"type": "cross", "value": 10}, "liqPx": "45000"}}
      ],
      "marginSummary": {"accountValue": "100000", "totalMarginUsed": "5000", "totalNtlPos": "75000", "totalRawUsd": "100000"}
    },
    "openOrders": [
      {"coin": "BTC", "oid": 123, "side": "A", "sz": "0.5", "limitPx": "52000", "timestamp": 1234567890}
    ]
  }
}
```

### Leaderboard Response Format (GET /leaderboard)
```json
{
  "leaderboardRows": [
    {
      "ethAddress": "0x...",
      "displayName": "TraderName",
      "accountValue": "1000000",
      "windowPerformances": [
        ["allTime", {"roi": "2.5", "vlm": "50000000", "pnl": "2500000"}],
        ["month", {"roi": "0.15", "vlm": "5000000", "pnl": "150000"}],
        ["week", {"roi": "0.05", "vlm": "1000000", "pnl": "50000"}],
        ["day", {"roi": "0.01", "vlm": "100000", "pnl": "10000"}]
      ]
    }
  ]
}
```

---

## 4. On-Chain Data Sources (External — Working)

### CBBI (colintalkscrypto.com)
| Endpoint | Purpose |
|----------|---------|
| `https://colintalkscrypto.com/cbbi/data/latest.json` | Current CBBI + all components |
| `https://colintalkscrypto.com/cbbi/data/history.json` | Historical CBBI |
| `https://colintalkscrypto.com/cbbi/data/components.json` | Component breakdown |

### Fear & Greed (alternative.me)
| Endpoint | Purpose |
|----------|---------|
| `https://api.alternative.me/fng/?limit=1` | Current index |
| `https://api.alternative.me/fng/?limit=30` | 30-day history |

### Coin Metrics (Community CSV — GitHub)
| Source | Purpose |
|--------|---------|
| `https://raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv` | Daily BTC metrics: PriceUSD, CapMrktCurUSD, AdrActCnt, TxCnt, SplyCur, BlkCnt, DiffMean, HashRate, FlowIn, FlowOut, NetFlow, Supply |

### Blockchain.info
| Endpoint | Purpose |
|----------|---------|
| `https://api.blockchain.info/stats` | Network stats: hash_rate, difficulty, n_blocks_total, n_btc_mined, trade_volume_btc, market_price_usd |
| `https://api.blockchain.info/charts/{metric}?timespan=1day&format=json` | Charts: hash-rate, difficulty, n-transactions, etc. |

### Bitview (bitview.space)
| Endpoint | Purpose |
|----------|---------|
| `https://bitview.space/api/v1/sopr` | SOPR |
| `https://bitview.space/api/v1/sopr/sth` | STH-SOPR |
| `https://bitview.space/api/v1/sopr/lth` | LTH-SOPR |

---

## 5. Redis Event Bus (Internal)

### Channels
- `events:trader_positions` — Position updates (internal: local dispatch only)
- `events:ohlcv` — Candle updates
- `events:signals` — Signal events
- `events:leaderboard` — Leaderboard snapshots
- `events:mark_price` — Mark price
- `events:trading_signal` — Raw trading signal
- `events:coin_metrics`, `events:fear_greed_index`, `events:cbbi_index` — On-chain
- `events:*` — Wildcard for external consumers

### Local Dispatch (In-Process)
High-volume events (`trader_positions`) use `local_only=True` — bypasses Redis entirely, dispatched directly to local handlers via `_dispatch_local_bulk` (wave-based, semaphore-limited).

---

## 6. MongoDB Collections (market_scraper database)

| Collection | Purpose | Key Indexes | TTL |
|------------|---------|-------------|-----|
| `events` | Raw event audit log | (timestamp:-1, event_type:1, source:1), correlation_id, event_id (unique) | 2 days |
| `btc_candles_1m` | 1m OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `btc_candles_5m` | 5m OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `btc_candles_15m` | 15m OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `btc_candles_1h` | 1h OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `btc_candles_4h` | 4h OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `btc_candles_1d` | 1d OHLCV | (symbol:1, timestamp:-1) | 30 days |
| `leaderboard_history` | Scored trader snapshots | (symbol:1, fetch_time:-1) | 90 days |
| `leaderboard_raw` | Full 39K raw snapshots | (symbol:1, fetch_time:-1) | 7 days |
| `trader_current_state` | Latest position per trader | (eth:1, symbol:1) unique | 30 days |
| `trader_positions` | Position history (time-series) | (eth:1, t:-1) | 30 days |
| `trader_scores` | Score history | (eth:1, fetch_time:-1) | 90 days |
| `trader_signals` | Per-trader signals | (eth:1, t:-1) | 30 days |
| `signals` | Aggregated BUY/SELL/NEUTRAL | (symbol:1, t:-1) | 30 days |
| `mark_prices` | Mark price history | (symbol:1, t:-1) | 30 days |
| `trades` | Raw trade data | (symbol:1, t:-1) | 7 days |
| `orderbook` | Orderbook snapshots | (symbol:1, t:-1) | 7 days |
| `cbbi_index` | CBBI confidence + components | (t:-1) | 90 days |
| `fear_greed_index` | Fear & Greed | (t:-1) | 90 days |
| `coin_metrics` | Coin Metrics daily | (t:-1) | 90 days |
| `blockchain_chart` | Blockchain.info charts | (t:-1) | 90 days |
| `exchange_flow` | Exchange flow data | (t:-1) | 90 days |

---

## 7. Systemd Service (Production)

```ini
# /etc/systemd/system/market-scraper.service
WorkingDirectory=/home/administrator/githubrepo/cryptoOS/market-scraper
Environment="PATH=/home/administrator/githubrepo/cryptoOS/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/administrator/githubrepo/cryptoOS/.venv/bin/python -m market_scraper server --host 127.0.0.1 --port 3845
Restart=always
RestartSec=15
MemoryMax=768M
MemoryHigh=600M
CPUQuota=70%
WatchdogSec=300
NotifyAccess=all
```

### Liveness Server (separate thread, port 3846)
Independent of asyncio event loop — always responds even when main loop blocked.

---

## 8. Key Configuration (market_config.yaml)

```yaml
# Daily leaderboard fetch (1 hour default)
storage:
  refresh_interval: 3600

# Trader tracking
filters:
  tiered_enabled: true
  max_count: 200
  tiers:
    - name: whale
      max_slots: 50
      min_account_value: 1000000
      require_positive: ["month"]
    - name: alpha
      max_slots: 50
      min_account_value: 100000
      min_roi_month: 0.05
      min_roi_all_time: 0.20
      require_positive: ["week", "month"]
    - name: grinder
      max_slots: 50
      min_account_value: 10000
      min_roi_month: 0.10
      min_roi_all_time: 0.50
      require_positive: ["week", "month"]
    - name: momentum
      max_slots: 50
      min_account_value: 10000
      min_roi_day: 0.01
      min_roi_week: 0.03
      require_positive: ["day", "week"]

# Trader WS (serial mode — 1 client, 10 traders, 60s dwell)
trader_ws:
  max_clients: 5
  subscriptions_per_client: 10
  serial_mode: true
  client_dwell_seconds: 60
```

---

## 9. Files to Preserve / Reference for Fresh Start

| File | Reason |
|------|--------|
| `market-scraper/config/market_config.yaml` | All scoring, filtering, tier, cadence config |
| `market-scraper/src/market_scraper/core/config.py` | Pydantic Settings with env loading |
| `market-scraper/src/market_scraper/storage/models.py` | Clean MongoDB models with short field names |
| `market-scraper/src/market_scraper/core/events.py` | StandardEvent definition |
| `market-scraper/src/market_scraper/event_bus/redis_bus.py` | Optimized local+Redis hybrid dispatch |
| `market-scraper/src/market_scraper/storage/mongo_repository.py` | Motor + sync pymongo bulk writes |
| `market-scraper/src/market_scraper/connectors/hyperliquid/client.py` | HTTP client for info API |
| `market-scraper/src/market_scraper/connectors/hyperliquid/parsers.py` | webData2, clearinghouse, leaderboard parsers |
| `market-scraper/src/market_scraper/utils/hyperliquid.py` | Shared utilities: parse_window_performances, extract_roi, etc. |
| `market-scraper/src/market_scraper/api/routes/*.py` | All REST endpoints (keep for API contract) |
| `market-scraper/src/market_scraper/streaming/websocket_server.py` | WebSocket server protocol |
| `market-scraper/tests/unit/connectors/test_trader_ws.py` | Unit tests for position logic |

---

## 10. Files to DELETE in Fresh Start

| File | Reason |
|------|--------|
| `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py` | **Replace entirely** — serial mode, complex batching, dead code |
| `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py` | **Replace** — new daily fetch + tiered filter logic |
| `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/candles.py` | Keep only if needed (candles already via CollectorManager) |
| `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/manager.py` | Keep — market data WS is fine |
| `market-scraper/src/market_scraper/orchestration/lifecycle.py` | **Rewrite** — new daily cadence flow |
| `market-scraper/src/market_scraper/processors/position_inference.py` | **Delete** — not needed with live positions |
| `market-scraper/src/market_scraper/processors/trader_scoring.py` | **Delete** — scoring happens in leaderboard fetch |
| `market-scraper/src/market_scraper/processors/signal_generation.py` | **Delete** — signal generation in smart-money-signal-system |
| `market-scraper/src/market_scraper/archival/` | **Delete** — not needed |
| `smart-money-signal-system/` | **Keep separate** — not part of market-scraper |

---

## 11. Environment Variables (`.env`)

```bash
MONGO__URL=mongodb+srv://...
MONGO__DATABASE=market_scraper
REDIS__URL=redis://localhost:6379
HYPERLIQUID__SYMBOL=BTC
HYPERLIQUID__ENABLED=true
BINANCE_CREDENTIAL_ENCRYPTION_KEY=...
LOG_LEVEL=INFO
LOG_FORMAT=json
```