# Smart Money Signal System

Real-time trading signal generation from whale position tracking on Hyperliquid.

## Architecture

```
market-scraper                    signal-system
     │                                 │
     │  Redis Pub/Sub                  │
     │  "events:trader_positions"  ──►│
     │  "events:scored_traders"    ──►│
     │  "events:candles"           ──►│
     │                                 │
     │                           ┌─────┴─────┐
     │                           │           │
     │                      Signal      Whale Alert
     │                    Processor     Detector
     │                           │           │
     │                           └─────┬─────┘
     │                                 │
     │                           Weighting
     │                            Engine
     │                                 │
     └─────────────────────────────────┘
                      │
                 FastAPI (port 4341)
                      │
              /api/v1/signals/*
              /api/v1/alerts/*
              /api/v1/whales/*
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
- Stores signals and alerts via SignalStore

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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component stats |
| `/api/v1/signals/latest` | GET | Latest trading signal |
| `/api/v1/signals/history` | GET | Signal history (up to 100) |
| `/api/v1/signals/stats` | GET | Signal processor statistics |
| `/api/v1/signals/store/stats` | GET | Signal store statistics |
| `/api/v1/alerts/latest` | GET | Latest whale alert |
| `/api/v1/alerts/history` | GET | Alert history |
| `/api/v1/alerts/active` | GET | Active (non-expired) alerts |
| `/api/v1/whales/stats` | GET | Whale detector statistics |

## Setup

### Requirements

- Python 3.10+
- Redis server
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
REDIS_URL=redis://localhost:6379/0
REDIS_CHANNEL_PREFIX=events

# API
API_HOST=0.0.0.0
API_PORT=4341

# Signal
SYMBOL=BTC
```

### Running

```bash
# Run API server with event processing
uv run python -m signal_system

# Or run in server-only mode
uv run python -m signal_system server
```

### Development

```bash
# Run tests
uv run pytest tests/ -v

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

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
| `events:candles` | OHLCV | Candle data for regime detection |

## License

MIT
