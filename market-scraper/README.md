# Market Scraper v2

Real-time cryptocurrency market data collection system for Hyperliquid with trader tracking, signal generation, and Bitcoin on-chain metrics.

## Overview

A production-ready market data system that collects real-time data from Hyperliquid, tracks top traders, generates trading signals, and aggregates Bitcoin on-chain metrics. Built with an event-driven architecture for scalability and maintainability.

## What's Implemented

### Data Collection (Collectors)

| Collector | Description | Storage Optimization |
|-----------|-------------|---------------------|
| **Candles** | OHLCV candle data (1m, 5m, 15m, 1h, 4h, 1d) via HTTP backfill | Standard |
| **Leaderboard** | Top trader rankings (hourly) | Standard |
| **Trader WS** | Real-time position tracking via WebSocket | 85% reduction (event-driven saves) |

**Note:** Individual trades and orderbook data are NOT collected. The system focuses on trader positions for signal generation, not market microstructure. Price data comes from OHLCV candles.

### Data Processing (Processors)

| Processor | Description |
|-----------|-------------|
| **PositionInferenceProcessor** | Infers trader positions from leaderboard (89% accuracy) |
| **TraderScoringProcessor** | Multi-factor trader scoring |
| **SignalGenerationProcessor** | BUY/SELL/NEUTRAL signal generation |

### On-Chain Data Connectors

| Connector | Description | Update Frequency |
|-----------|-------------|------------------|
| **BlockchainInfo** | Hash rate, difficulty, block height, supply | On-demand |
| **FearGreed** | Fear & Greed Index (sentiment) | Daily |
| **CoinMetrics** | Active addresses, transaction count, supply | On-demand |
| **CBBI** | Bitcoin Bull Run Index (9 components) | Daily |
| **Bitview** | SOPR, NUPL, MVRV, HODL Waves | On-demand |
| **ExchangeFlow** | Exchange inflows/outflows, netflow | On-demand |

**Note:** On-chain connectors do NOT return price data. Use Hyperliquid candles for price information.

### API Endpoints

#### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe |
| GET | `/health/status` | Detailed health status |

#### Markets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/markets` | List available markets |
| GET | `/api/v1/markets/{symbol}` | Get market data |
| GET | `/api/v1/markets/{symbol}/history` | Get OHLCV history |

#### Traders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/traders` | List tracked traders |
| GET | `/api/v1/traders/{address}` | Trader details + positions |
| GET | `/api/v1/traders/{address}/positions` | Position history |
| GET | `/api/v1/traders/{address}/signals` | Trader's signals |

#### Signals
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/signals` | Signal history |
| GET | `/api/v1/signals/current` | Current aggregated signal |
| GET | `/api/v1/signals/stats` | Signal statistics |
| GET | `/api/v1/signals/{id}` | Signal by ID (24-char hex) |

#### Connectors
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/connectors` | List all connectors |
| GET | `/api/v1/connectors/{name}` | Connector status |
| POST | `/api/v1/connectors/{name}/start` | Start connector |
| POST | `/api/v1/connectors/{name}/stop` | Stop connector |

#### CBBI (Bitcoin Bull Run Index)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/cbbi` | Current CBBI confidence + components |
| GET | `/api/v1/cbbi/components` | All component breakdown |
| GET | `/api/v1/cbbi/components/{name}` | Specific component data |

#### On-Chain Metrics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/onchain/btc/summary` | Unified BTC on-chain metrics |
| GET | `/api/v1/onchain/btc/network` | Hash rate, difficulty, block height |
| GET | `/api/v1/onchain/btc/sentiment` | Fear & Greed + CBBI confidence |
| GET | `/api/v1/onchain/btc/valuation` | MVRV, Puell, NUPL, etc. |
| GET | `/api/v1/onchain/btc/activity` | Active addresses, transaction count |
| GET | `/api/v1/onchain/btc/sopr` | Spent Output Profit Ratio |
| GET | `/api/v1/onchain/btc/exchange-flows` | Exchange inflows/outflows |
| GET | `/api/v1/onchain/btc/nupl` | Net Unrealized Profit/Loss |
| GET | `/api/v1/onchain/btc/mvrv` | Market Value to Realized Value |

#### WebSocket
| Endpoint | Description |
|----------|-------------|
| `/ws?channel=traders` | Trader position/score updates |
| `/ws?channel=signals` | Trading signal alerts |

### Storage

- **MongoDB**: Persistent storage with optimized models
- **MemoryRepository**: In-memory storage for testing/development

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB (for persistent storage)
- Redis (optional, for distributed event bus)
- `uv` package manager

### Installation

```bash
# Install dependencies
uv sync

# Copy environment file
cp .env.example .env

# Edit .env with your settings
# Set MONGO__URL to your MongoDB connection string
```

### Running the Server

#### Quick Start (from project root)

```bash
# Start both servers (market-scraper + signal-system)
cd /home/muham/development/cryptodata
./scripts/start-all.sh --background

# Check status
./scripts/status.sh

# Stop all servers
./scripts/stop-all.sh
```

#### Manual Start

```bash
# Start with default settings (BTC)
uv run python -m market_scraper server

# Start with specific symbol
uv run python -m market_scraper server --symbol ETH

# Start API only (no collectors)
uv run python -m market_scraper server --no-collectors

# Custom host/port
uv run python -m market_scraper server --host 0.0.0.0 --port 8080
```

#### Production (systemd)

```bash
# Install service (from project root)
sudo cp systemd/market-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable market-scraper.service
sudo systemctl start market-scraper.service

# Check status
sudo systemctl status market-scraper.service

# View logs
sudo journalctl -u market-scraper.service -f
```

See [systemd/README.md](../systemd/README.md) for detailed instructions.

### CLI Commands

```bash
# Show help
uv run python -m market_scraper --help

# Check system health
uv run python -m market_scraper health

# Show configuration
uv run python -m market_scraper config

# Connector management
uv run python -m market_scraper collectors status
uv run python -m market_scraper collectors start --all
uv run python -m market_scraper collectors stop --all

# Trader management
uv run python -m market_scraper traders list
uv run python -m market_scraper traders track <address>
uv run python -m market_scraper traders untrack <address>
```

## Configuration

Configuration is via environment variables or `.env` file, plus YAML for advanced settings:

```bash
# MongoDB (required for persistence)
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper

# Redis (optional, for distributed setups - now default when available)
REDIS__URL=redis://localhost:6379

# Hyperliquid Settings
HYPERLIQUID__ENABLED=true
HYPERLIQUID__SYMBOL=BTC           # Only save data for this symbol

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### YAML Configuration (Advanced)

The system uses `config/market_config.yaml` for advanced configuration:

```bash
# View current configuration
uv run python -m market_scraper config
```

### Scheduler Configuration

The scheduler runs periodic background tasks. Configure in `config/market_config.yaml`:

```yaml
scheduler:
  enabled: true
  tasks:
    leaderboard_refresh:
      enabled: true
      interval_seconds: 3600  # 1 hour
    health_check:
      enabled: true
      interval_seconds: 600  # 10 minutes
    connector_health:
      enabled: true
      interval_seconds: 600  # 10 minutes
    data_cleanup:
      enabled: false  # Use MongoDB TTL indexes instead
```

### Data Archival Configuration

Archive data before TTL deletion for long-term storage:

```yaml
archival:
  enabled: false  # Enable via environment or config override
  schedule: "monthly"
  compression:
    algorithm: "zstd"
    level: 3  # 1=fastest, 22=best ratio
  git_lfs:
    repo_url: "${ARCHIVE_REPO_URL}"
    branch: "main"
  collections:
    - trader_positions
    - signals
    - leaderboard_history
    - candles
```

**Run archival manually:**
```bash
# Archive specific collections
uv run python scripts/run_archive.py --collections trader_positions signals

# Archive all configured collections
uv run python scripts/run_archive.py --all --push
```

**Restore from archive:**
```python
from market_scraper.archival import Compressor

compressor = Compressor()
data = compressor.decompress_from_file(Path("/data/archives/positions_202401.zst"))
```

### Position Inference Configuration

Configure position inference thresholds:

```yaml
position_inference:
  enabled: true
  confidence_threshold: 0.5
  indicators:
    day_roi_threshold: 0.0001
    pnl_ratio_threshold: 0.001
    day_volume_threshold: 100000
```

### Buffer Configuration

Configure event buffering for MongoDB writes:

```yaml
buffer:
  flush_interval: 50.0      # Seconds between flushes
  max_size: 100              # Max events before forced flush
  broadcast_batch_size: 100
  broadcast_batch_timeout_ms: 10.0
```

### Symbol Filtering

**Important**: The system only saves data for the configured symbol (default: BTC). This is enforced at the collector level for maximum efficiency.

```bash
# Track ETH instead
HYPERLIQUID__SYMBOL=ETH uv run python -m market_scraper server
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Market Scraper v2                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ Collectors  │───▶│  Event Bus  │───▶│ Processors  │         │
│  │             │    │ (Memory/    │    │             │         │
│  │ - Candles   │    │  Redis)     │    │ - Scoring   │         │
│  │ - Leaderboard    └──────┬──────┘    │ - Signals   │         │
│  │             │           │           │ - Positions  │         │
│  └─────────────┘           │           └──────┬──────┘         │
│                            ▼                  │                  │
│                    ┌─────────────┐            │                  │
│                    │   Storage   │◀───────────┘                  │
│                    │ (Repository)│                              │
│                    └──────┬──────┘                              │
│                           │                                      │
│                           ▼                                      │
│                    ┌─────────────┐                              │
│                    │  REST API   │                              │
│                    │  (FastAPI)  │                              │
│                    └─────────────┘                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Background Tasks (Scheduler)                            │   │
│  │  - Leaderboard Refresh  - Health Check                  │   │
│  │  - Connector Health   - Data Cleanup                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Models

### Collections

| Collection | Description |
|------------|-------------|
| `{symbol}_candles_{interval}` | OHLCV candles (e.g., `btc_candles_1h`) |
| `trader_positions` | Position snapshots |
| `trader_scores` | Score history |
| `tracked_traders` | Currently tracked traders |
| `signals` | Generated signals |
| `trader_signals` | Individual trader signals |
| `leaderboard_history` | Leaderboard snapshots |

### Field Naming (Optimized for Storage)

```python
# Candle model
{
    "t": datetime,     # Timestamp
    "o": 97000.0,      # Open price
    "h": 97100.0,      # High price
    "l": 96900.0,      # Low price
    "c": 97050.0,      # Close price
    "v": 15.5          # Volume
}

# Signal model
{
    "t": datetime,     # Timestamp
    "symbol": "BTC",
    "rec": "BUY",      # BUY, SELL, NEUTRAL
    "conf": 0.75,      # Confidence (0-1)
    "long_bias": 0.7,  # Long bias
    "short_bias": 0.3, # Short bias
    "net_exp": 0.4     # Net exposure
}
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/market_scraper

# Run specific test types
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/
```

## Input Validation

The API validates inputs for security and data integrity:

### Ethereum Addresses
- Format: `0x` followed by 40 hexadecimal characters
- Example: `0x6859da14835424957a1e6b397d8026b1d9ff7e1e`
- Invalid format returns HTTP 400

### Signal IDs
- Format: 24-character hexadecimal string (MongoDB ObjectId)
- Example: `507f1f77bcf86cd799439011`
- Invalid format returns HTTP 400

## Documentation

- [Documentation Index](DOCUMENTATION.md) - Complete documentation overview
- [Data Storage](docs/DATA_STORAGE.md) - MongoDB collections and schemas
- [Architecture Overview](docs/architecture/overview.md) - System design and components
- [Connector Architecture](docs/architecture/connectors.md) - How to add new data sources
- [Event System](docs/architecture/event_system.md) - Event-driven architecture
- [Quick Start Guide](docs/guides/quickstart.md) - Get up and running
- [Development Guide](docs/guides/development.md) - Testing and contributing
- [Deployment Guide](docs/guides/deployment.md) - Production deployment
- [CBBI Guide](docs/CBBI_GUIDE.md) - Bitcoin Bull Run Index documentation
- [Trader Filter Guide](docs/TRADER_FILTER_GUIDES.md) - Trader scoring configuration

## API Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

MIT License
