# Hyperliquid API Repository

Complete Hyperliquid API documentation with download scripts for all endpoints including both cached CloudFront data and official Hyperliquid API.

## Repository Structure

```
hyperliquid/
├── README.md                          # Main documentation
├── HYPERLIQUID_ALL_ENDPOINTS.md       # Complete endpoint reference
├── scripts/
│   ├── download_all_hyperliquid_data.sh    # Download all CloudFront data
│   ├── hyperliquid_api/                   # Hyperliquid official API scripts
│   │   ├── download_all_hyperliquid_api.sh # Download all API data
│   │   ├── download_*.sh                  # 55+ individual scripts
│   │   ├── websocket_subscribe.sh         # WebSocket subscription
│   │   └── websocket_subscribe.py        # Python WebSocket client
│   └── ...
├── docs/                               # API documentation
│   ├── API_*.md                         # CloudFront API docs
│   └── hyperliquid_api/                  # Official API docs
│       ├── README.md                     # Hyperliquid API overview
│       ├── API_*.md                      # 20+ endpoint docs
│       └── API_WEBSOCKET.md              # WebSocket documentation
├── data/                               # Downloaded JSON data
│   └── hyperliquid/                     # Official API data
├── .gitignore
└── LICENSE
```

## Quick Start

### Download All CloudFront Data

```bash
./scripts/download_all_hyperliquid_data.sh
```

### Download All Official API Data

```bash
./scripts/hyperliquid_api/download_all_hyperliquid_api.sh 0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2
```

## Two Data Sources

### 1. CloudFront Cached Data (ASXN)
Historical cached data with larger time series.

| # | Endpoint | Size | Description |
|---|----------|------|-------------|
| 1 | `/cumulative_inflow` | 70 KB | Cumulative net inflow |
| 2 | `/daily_inflow` | 60 KB | Daily deposits/withdrawals |
| 3 | `/cumulative_usd_volume` | 64 KB | Cumulative trading volume |
| 4 | `/daily_usd_volume` | 70 KB | Daily trading volume |
| 5 | `/cumulative_trades` | 59 KB | Cumulative number of trades |
| 6 | `/daily_unique_users` | 59 KB | Daily active unique users |
| 7 | `/cumulative_new_users` | 86 KB | New users over time |
| 8 | `/open_interest` | 11.9 MB | Open interest by coin |
| 9 | `/funding_rate` | 11.7 MB | Funding rates by coin |
| 10 | `/liquidity_by_coin` | 47 MB | Liquidity data |
| 11 | `/daily_notional_liquidated_by_coin` | 5.7 MB | Liquidations by coin |
| 12 | `/largest_user_depositors` | 84 KB | Top 1,000 deposits |
| 13 | `/largest_liquidated_notional_by_user` | 80 KB | Top 1,000 liquidations |
| 14 | `/largest_user_trade_count` | 77 KB | Top 1,000 trade counts |
| 15 | `/largest_users_by_usd_volume` | 84 KB | Top 1,000 by volume |

### 2. Official Hyperliquid API
Real-time data via REST and WebSocket.

**REST API:** `https://api.hyperliquid.xyz/info`
**WebSocket:** `wss://api.hyperliquid.xyz/trading`

#### User Data Endpoints

| Endpoint | Description |
|----------|-------------|
| `clearinghouseState` | Account value, positions, margin |
| `openOrders` | Pending orders |
| `fills` | Recent trades |
| `userFills` | User fills (detailed) |
| `historicalOrders` | Order history |
| `accountState` | Account state |
| `userFunding` | Funding payments |
| `crossMarginSummary` | Cross margin summary |
| `effectiveLeverage` | Effective leverage |
| `wallet` | Wallet balance |
| `ledger` | Transaction ledger |
| `depositHistory` | Deposit history |
| `withdrawHistory` | Withdrawal history |

#### Market Data Endpoints

| Endpoint | Description | Parameters |
|----------|-------------|------------|
| `orderbook` | Order book | `coin` |
| `l2Book` | Full depth orderbook | `coin` |
| `ticker` | 24h ticker | `coin` |
| `trades` | Recent trades | `coin` |
| `marketTrades` | Market trades | `coin` |
| `candles` | OHLC candles | `coin`, `interval`, `startTime` |
| `fundingHistory` | Funding history | `coin` |
| `metaAndAssetCtxs` | Market metadata | - |
| `allMids` | All mark prices | - |

#### Staking Endpoints

| Endpoint | Description |
|----------|-------------|
| `stakingBalance` | Staking balance |
| `stakingHistory` | Staking history |
| `stakingUnstakeable` | Unstakeable amount |
| `delegationBalance` | Delegation balance |
| `delegationHistory` | Delegation history |

#### Spot Market Endpoints

| Endpoint | Description |
|----------|-------------|
| `spotClearinghouseState` | Spot balances |
| `spotOrders` | Spot orders |
| `spotFills` | Spot trades |
| `spotMeta` | Spot metadata |
| `spotMids` | Spot prices |
| `spotOrderbook` | Spot orderbook |
| `spotKlines` | Spot candles |

#### WebSocket Channels

**Public:**
- `trades` - Real-time trades
- `book` - Orderbook updates
- `candle` - Candle updates
- `webData2` - General updates

**Private (Auth Required):**
- `orderUpdates` - Order status
- `userFills` - User fills
- `user` - User state

#### Global Data Endpoints

| Endpoint | Description |
|----------|-------------|
| `leaderboard` | Trader leaderboard |
| `vaults` | All vaults |
| `liquidationCandidates` | Liquidation candidates |
| `recentTransactions` | Recent transactions |
| `exchangeStatus` | Exchange status |
| `userPoints` | User points |
| `feeSchedule` | Fee schedule |
| `healthInfo` | Account health |
| `userRateLimit` | Rate limit status |

## Script Usage

### Download All Official API Data

```bash
./scripts/hyperliquid_api/download_all_hyperliquid_api.sh <USER_ADDRESS>
```

### Download Single Endpoint

```bash
./scripts/hyperliquid_api/download_clearinghouse_state.sh <USER_ADDRESS>
./scripts/hyperliquid_api/download_ticker.sh BTC
./scripts/hyperliquid_api/download_orderbook.sh BTC
./scripts/hyperliquid_api/download_candles.sh BTC 1h
```

### WebSocket Subscription

```bash
# Python (recommended)
python3 scripts/hyperliquid_api/websocket_subscribe.py trades BTC

# Bash (requires websocat)
./scripts/hyperliquid_api/websocket_subscribe.sh trades BTC
```

## API Documentation

### CloudFront Data Docs
See `docs/API_*.md` for detailed documentation.

### Official API Docs
See `docs/hyperliquid_api/` for comprehensive documentation:

- [README](docs/hyperliquid_api/README.md) - Complete overview
- [Clearinghouse State](docs/hyperliquid_api/API_CLEARINGHOUSE_STATE.md)
- [Open Orders](docs/hyperliquid_api/API_OPEN_ORDERS.md)
- [Fills](docs/hyperliquid_api/API_FILLS.md)
- [Orderbook](docs/hyperliquid_api/API_ORDERBOOK.md)
- [L2 Book](docs/hyperliquid_api/API_L2_BOOK.md)
- [Ticker](docs/hyperliquid_api/API_TICKER.md)
- [Candles](docs/hyperliquid_api/API_CANDLES.md)
- [Funding History](docs/hyperliquid_api/API_FUNDING_HISTORY.md)
- [User Funding](docs/hyperliquid_api/API_USER_FUNDING.md)
- [Spot Data](docs/hyperliquid_api/API_SPOT_CLEARINGHOUSE_STATE.md)
- [Staking](docs/hyperliquid_api/API_STAKING.md)
- [Delegation](docs/hyperliquid_api/API_DELEGATION.md)
- [Wallet & History](docs/hyperliquid_api/API_WALLET_HISTORY.md)
- [User Points](docs/hyperliquid_api/API_USER_POINTS.md)
- [WebSocket](docs/hyperliquid_api/API_WEBSOCKET.md)

## Requirements

- `curl` - For downloading REST data
- `bash` - For running scripts
- `python3` - For WebSocket client
- `websocat` - Optional, for WebSocket in bash

## Features

- ✅ No authentication required for most endpoints
- ✅ 55+ download scripts
- ✅ 20+ detailed API documentation files
- ✅ WebSocket subscription support
- ✅ Python and bash clients
- ✅ GitHub-ready structure
- ✅ Comprehensive rate limit documentation

## License

MIT License
