# Hyperliquid API Documentation

Complete reference for Hyperliquid exchange APIs including REST endpoints and WebSocket subscriptions.

## Overview

Hyperliquid provides comprehensive APIs for:
- **User Data** - Account state, positions, orders, fills, history
- **Market Data** - Orderbooks, trades, candles, funding rates
- **Staking** - HYPE token staking and delegation
- **Real-time** - WebSocket subscriptions

## API Base URLs

| Environment | REST API | WebSocket |
|------------|----------|-----------|
| Mainnet | `https://api.hyperliquid.xyz/info` | `wss://api.hyperliquid.xyz/trading` |

## Quick Start

### Download All User Data

```bash
./scripts/hyperliquid_api/download_all_hyperliquid_api.sh 0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2
```

### Download Single Endpoint

```bash
./scripts/hyperliquid_api/download_clearinghouse_state.sh 0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2
./scripts/hyperliquid_api/download_ticker.sh BTC
./scripts/hyperliquid_api/download_orderbook.sh BTC
```

### Subscribe to WebSocket

```bash
# Using Python
python3 scripts/hyperliquid_api/websocket_subscribe.py trades BTC

# Using Bash (requires websocat)
./scripts/hyperliquid_api/websocket_subscribe.sh trades BTC
```

## Endpoints Reference

### User Data Endpoints

| Endpoint | Description | Script |
|----------|-------------|--------|
| `clearinghouseState` | Account value, positions, margin | [download_clearinghouse_state.sh](../../scripts/hyperliquid_api/download_clearinghouse_state.sh) |
| `openOrders` | Pending orders | [download_open_orders.sh](../../scripts/hyperliquid_api/download_open_orders.sh) |
| `fills` | Recent trades | [download_fills.sh](../../scripts/hyperliquid_api/download_fills.sh) |
| `userFills` | User fills (detailed) | [download_user_fills.sh](../../scripts/hyperliquid_api/download_user_fills.sh) |
| `historicalOrders` | Order history | [download_historical_orders.sh](../../scripts/hyperliquid_api/download_historical_orders.sh) |
| `accountState` | Account state | [download_account_state.sh](../../scripts/hyperliquid_api/download_account_state.sh) |
| `userFunding` | Funding payments | [download_user_funding.sh](../../scripts/hyperliquid_api/download_user_funding.sh) |
| `crossMarginSummary` | Cross margin summary | [download_cross_margin_summary.sh](../../scripts/hyperliquid_api/download_cross_margin_summary.sh) |
| `effectiveLeverage` | Effective leverage | [download_effective_leverage.sh](../../scripts/hyperliquid_api/download_effective_leverage.sh) |

### Wallet & History Endpoints

| Endpoint | Description | Script |
|----------|-------------|--------|
| `wallet` | Wallet balance | [download_wallet.sh](../../scripts/hyperliquid_api/download_wallet.sh) |
| `ledger` | Transaction ledger | [download_ledger.sh](../../scripts/hyperliquid_api/download_ledger.sh) |
| `depositHistory` | Deposit history | [download_deposit_history.sh](../../scripts/hyperliquid_api/download_deposit_history.sh) |
| `withdrawHistory` | Withdrawal history | [download_withdraw_history.sh](../../scripts/hyperliquid_api/download_withdraw_history.sh) |

### Market Data Endpoints

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

### Spot Market Endpoints

| Endpoint | Description | Parameters |
|----------|-------------|------------|
| `spotClearinghouseState` | Spot balances | `user` |
| `spotOrders` | Spot orders | `user` |
| `spotFills` | Spot trades | `user` |
| `spotMeta` | Spot market metadata | - |
| `spotMids` | Spot mark prices | - |
| `spotOrderbook` | Spot orderbook | `symbol` |
| `spotKlines` | Spot candles | `symbol`, `interval`, `startTime` |

### Staking Endpoints

| Endpoint | Description | Parameters |
|----------|-------------|------------|
| `stakingBalance` | Staking balance | `user` |
| `stakingHistory` | Staking history | `user` |
| `stakingUnstakeable` | Unstakeable amount | `user` |
| `delegationBalance` | Delegation balance | `user` |
| `delegationHistory` | Delegation history | `user` |

### Points & Rewards

| Endpoint | Description | Parameters |
|----------|-------------|------------|
| `userPoints` | User points | `user` |
| `feeSchedule` | Fee schedule | `user` |
| `userRateLimit` | Rate limit status | `user` |
| `healthInfo` | Account health | `user` |
| `userWhale` | Whale status | `user` |

### Global Data Endpoints

| Endpoint | Description |
|----------|-------------|
| `leaderboard` | Trader leaderboard |
| `referralLeaderboard` | Referral leaderboard |
| `vaults` | All vaults |
| `vaultUsers` | Vault users |
| `liquidationCandidates` | Liquidation candidates |
| `recentTransactions` | Recent transactions |
| `communityInfo` | Community info |
| `exchangeStatus` | Exchange status |
| `updateTimes` | Update timestamps |
| `gasTracker` | Gas tracking |
| `marketHype` | Market hype data |
| `airdropMetadata` | Airdrop info |
| `tokenConfig` | Token configuration |

## Candle Intervals

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `1h` | 1 hour |
| `4h` | 4 hours |
| `1d` | 1 day |

## WebSocket Channels

### Public Channels

| Channel | Description | Parameters |
|---------|-------------|------------|
| `trades` | Real-time trades | `coin` |
| `book` | Orderbook updates | `coin` |
| `candle` | Candle updates | `coin`, `interval` |
| `webData2` | General updates | - |

### Private Channels (Auth Required)

| Channel | Description |
|---------|-------------|
| `orderUpdates` | Order status updates |
| `userFills` | User fill notifications |
| `user` | User state changes |

## Authentication

Most endpoints are public and don't require authentication. For private data (user-specific), you need:

1. Sign a message with your private key
2. Include the signature in the request header

See [Hyperliquid SDK](https://github.com/hyperliquid-xyz/hyperliquid-js) for authentication examples.

## Rate Limits

- REST API: Check `userRateLimit` endpoint
- WebSocket: 30 requests/second max
- Maximum 100 subscriptions per connection

## Scripts Usage

### Download All Data

```bash
./scripts/hyperliquid_api/download_all_hyperliquid_api.sh <USER_ADDRESS>
```

### Download Individual Endpoint

```bash
./scripts/hyperliquid_api/download_<endpoint>.sh <PARAMETER> [OUTPUT_FILE]
```

### WebSocket Subscription

```bash
# Python (recommended)
python3 scripts/hyperliquid_api/websocket_subscribe.py <channel> <coin> [max_messages]

# Example
python3 scripts/hyperliquid_api/websocket_subscribe.py trades BTC 100
```

## Response Format

All endpoints return JSON with string values for precision:

```json
{
  "accountValue": "1513034.031499",
  "positionValue": "72934.6314"
}
```

Parse strings to floats for calculations:
```python
account_value = float(data["accountValue"])
```

## Data Directory

Downloaded data is saved to:
- `data/hyperliquid/` - Main data directory

## License

MIT License
