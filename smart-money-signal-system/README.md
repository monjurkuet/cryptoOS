# Smart Money Signal System

Real-time trading signal generation from whale position tracking on Hyperliquid, now with reinforcement-learning based parameter tuning.

## What Changed Recently

The latest development cycle adds a full RL feedback loop around signal generation:

- **Outcome tracking** records how BUY/SELL signals perform after 1m, 5m, 15m, and 1h.
- **Mongo-backed outcome storage** persists those resolved outcomes in the `rl_outcomes` collection.
- **RL parameter server** loads the newest checkpoint at startup and serves live parameters thread-safely.
- **Offline retraining pipeline** can rebuild training data from historical signals + candles when outcome storage is empty.
- **New API endpoints** expose RL status, current params, recent outcomes, and background retraining.

## Architecture

```
market-scraper                    signal-system
     │                                 │
     │  Redis Pub/Sub                  │
     │  "events:trader_positions"  ──►│
     │  "events:scored_traders"    ──►│
     │  "events:ohlcv"           ──►│
     │  "events:mark_price"        ──►│
     │                                 │
     │                           ┌─────┴─────┐
     │                           │           │
     │                      Signal      Whale Alert
     │                    Processor     Detector
     │                           │           │
     │                           └─────┬─────┘
     │                                 │
     │                      Outcome Tracker
     │                      Outcome Store
     │                      RL Param Server
     │                                 │
     └─────────────────────────────────┘
                      │
                 FastAPI (port 4341)
                      │
              /api/v1/signals/*
              /api/v1/alerts/*
              /api/v1/whales/*
              /api/v1/rl/*
```

## Components

### Signal Generation Processor

Aggregates trader positions to generate trading signals:
- Tracks positions from scored traders
- Calculates long/short bias
- Generates BUY/SELL/NEUTRAL signals with confidence
- **Memory Management**: TTL-based cleanup (24h), max 10,000 traders

### Event Processor

Shared event processing logic for standalone and API modes:
- Handles trader position events
- Handles scored traders events
- Handles mark price events for reward resolution
- Stores signals and alerts via SignalStore
- Persists resolved outcomes via OutcomeStore

### Safe Conversions

Prevents crashes from malformed Redis data:
```python
from signal_system.utils.safe_convert import safe_float, safe_datetime

account_value = safe_float(payload.get("accountValue"), 0)  # Never raises
timestamp = safe_datetime(payload.get("timestamp"))  # Returns None on error
```

### Whale Alert Detector

Detects significant whale position changes:
- **CRITICAL**: Alpha Whale ($20M+) position change
- **HIGH**: 2+ whales change within 5 min
- **MEDIUM**: Aggregate whale bias flips 30%+
- **LOW**: Single whale position change
- **Memory Management**: 7-day TTL for position history, bounded alerts (500), bounded changes (1000)

### Weighting Engine

Multi-dimensional trader scoring:
- **Performance**: Sharpe, Sortino, consistency, drawdown, win rate, profit factor
- **Size**: 6 tiers (alpha_whale → small)
- **Recency**: Time decay (day/week/month)
- **Regime**: Market condition alignment

### ML Components

- **Market Regime Detector**: KMeans clustering for 6 regimes (deep_accumulation, early_bull, mid_bull, late_bull, distribution, bear)
  - **Memory Management**: Bounded history (max 1000 entries)
- **Feature Importance Analyzer**: RandomForest-based feature ranking

### RL Components

- **SignalOutcomeTracker**: Registers emitted signals and resolves outcome PnL at `60`, `300`, `900`, and `3600` seconds.
- **OutcomeStore**: Writes outcomes to MongoDB collection `rl_outcomes` under the `signal_system` database by default.
- **RLParameterServer**: Loads the latest checkpoint from `smart-money-signal-system/checkpoints/` and exposes current runtime params.
- **OfflineTrainer**: Replays stored outcomes through a Gymnasium environment and trains a PPO policy with PyTorch.
- **Retrain CLI**: Saves new `.pt` checkpoints and can push them straight back into the live API.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component stats |
| `/api/v1/signals/latest` | GET | Latest trading signal |
| `/api/v1/signals/history` | GET | Signal history (up to 100) |
| `/api/v1/signals/stats` | GET | Signal processor statistics |
| `/api/v1/signals/store/stats` | GET | Signal store statistics |
| `/api/v1/signal-system/signals/latest` | GET | Namespaced latest signal alias for shared-domain deployments |
| `/api/v1/signal-system/signals/history` | GET | Namespaced signal history alias |
| `/api/v1/signal-system/signals/stats` | GET | Namespaced signal stats alias |
| `/api/v1/signal-system/signals/store-stats` | GET | Namespaced signal-store stats alias |
| `/api/v1/alerts/latest` | GET | Latest whale alert |
| `/api/v1/alerts/history` | GET | Alert history |
| `/api/v1/alerts/active` | GET | Active (non-expired) alerts |
| `/api/v1/whales/stats` | GET | Whale detector statistics |
| `/api/v1/rl/status` | GET | RL parameter status + checkpoint metadata |
| `/api/v1/rl/params` | GET | Current runtime RL-tuned parameters |
| `/api/v1/rl/params` | PUT | Update runtime RL parameters |
| `/api/v1/rl/outcomes` | GET | Recent resolved signal outcomes |
| `/api/v1/rl/retrain` | POST | Trigger background retraining |
| `/api/v1/dashboard/signal-generator/overview` | GET | Combined dashboard overview |
| `/api/v1/dashboard/signal-generator/timeline` | GET | Normalized combined timeline |
| `/api/v1/dashboard/signal-generator/params/current` | GET | Current runtime params + checkpoint metadata |
| `/api/v1/dashboard/signal-generator/params/history` | GET | Runtime parameter event history |
| `/api/v1/dashboard/signal-generator/decisions` | GET | Explainability traces (emitted/suppressed) |

## Setup

### Requirements

- Python 3.11+
- Redis server
- MongoDB (recommended for RL outcome persistence)
- uv package manager

### Installation

```bash
cd smart-money-signal-system
uv sync
```

### Configuration

Create a `.env` file:

```env
# Redis
REDIS__URL=redis://localhost:6379/0
REDIS__CHANNEL_PREFIX=events

# MongoDB for RL outcomes
SIGNAL_MONGO__URL=mongodb://localhost:27017
SIGNAL_MONGO__DATABASE=signal_system

# API
API_HOST=0.0.0.0
API_PORT=4341
API_ROOT_PATH=/signal-system

# Signal
SYMBOL=BTC
```

For local direct access without a reverse-proxy prefix, set `API_ROOT_PATH=` (empty).

### Running

#### Quick Start (from project root)

```bash
# Start both servers together
cd /home/administrator/githubrepo/cryptoOS
./scripts/start-all.sh --background

# Check status
./scripts/status.sh
```

#### Manual Start

```bash
# Run standalone event processor + Redis subscriber
uv run python -m signal_system

# Run API server mode
uv run python -m signal_system server

# Trigger offline retraining
uv run python -m signal_system.rl.retrain --episodes 100

# Retrain and push fresh params to the running API
uv run python -m signal_system.rl.retrain --episodes 100 --push
```

#### Production (systemd)

```bash
# Install service (from project root)
sudo cp systemd/signal-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable signal-system.service
sudo systemctl start signal-system.service

# Check status
sudo systemctl status signal-system.service

# View logs
sudo journalctl -u signal-system.service -f
```

See [systemd/README.md](../systemd/README.md) for detailed instructions.

### Development

```bash
# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

## How To Use The RL Features

### 1. Start the system normally

The RL components are passive until data starts flowing:

- the API or standalone process loads the newest checkpoint from `smart-money-signal-system/checkpoints/`
- trader position events keep generating signals
- mark price events resolve signal outcomes over time
- resolved outcomes are written to MongoDB if configured

### 2. Inspect live RL state

```bash
curl http://localhost:4341/api/v1/rl/status
curl http://localhost:4341/api/v1/rl/params
curl "http://localhost:4341/api/v1/rl/outcomes?limit=20"
```

Typical uses:

- confirm whether a checkpoint was loaded
- inspect active `bias_threshold`, `conf_scale`, and `min_confidence`
- review recent realized PnL and win rate

### 3. Adjust runtime params manually

```bash
curl -X PUT http://localhost:4341/api/v1/rl/params \
  -H "Content-Type: application/json" \
  -d '{"bias_threshold": 0.25, "conf_scale": 1.2, "min_confidence": 0.35}'
```

Parameter meanings:

- `bias_threshold`: net-bias threshold before the system emits `BUY` or `SELL`
- `conf_scale`: multiplies confidence before clamping to `1.0`
- `min_confidence`: suppresses low-conviction signals

### 4. Run retraining

```bash
# CLI
uv run python -m signal_system.rl.retrain --episodes 200 --push

# Or via API
curl -X POST "http://localhost:4341/api/v1/rl/retrain?episodes=200"
```

Retraining behavior:

- first tries recent documents from `rl_outcomes`
- if none exist, backfills synthetic outcomes from `market_scraper.signals` plus candle collections
- saves a timestamped checkpoint into `smart-money-signal-system/checkpoints/`
- optionally pushes the trained params back into the running API

### 5. Watch for cold-start behavior

On a fresh system:

- `/api/v1/rl/status` may show no checkpoint path yet
- `/api/v1/rl/outcomes` may be empty
- the first meaningful retrain may synthesize outcomes from historical market-scraper data

## Signal Format

```json
{
  "symbol": "BTC",
  "action": "BUY",
  "confidence": 0.75,
  "long_bias": 0.65,
  "short_bias": 0.35,
  "net_bias": 0.30,
  "traders_long": 45,
  "traders_short": 23,
  "timestamp": "2026-02-25T10:30:00+00:00"
}
```

## Alert Format

```json
{
  "priority": "CRITICAL",
  "title": "Alpha Whale LONG",
  "description": "Alpha whale ($25.0M) changed BTC position",
  "detected_at": "2026-02-25T10:30:00+00:00",
  "expires_at": "2026-02-25T11:30:00+00:00",
  "changes": [
    {
      "address": "0x...",
      "tier": "alpha_whale",
      "coin": "BTC",
      "change_pct": 1.0,
      "account_value": 25000000
    }
  ]
}
```

## Integration with market-scraper

The signal-system subscribes to Redis events from the market-scraper:

| Channel | Event Type | Description |
|---------|------------|-------------|
| `events:trader_positions` | Position Update | Individual trader positions |
| `events:scored_traders` | Scores | Trader performance scores |
| `events:ohlcv` | OHLCV | Candle data for regime detection |
| `events:mark_price` | Mark Price | Resolves signal outcomes for RL training |

## License

MIT
