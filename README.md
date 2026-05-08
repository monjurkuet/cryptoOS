# cryptoOS

Cryptocurrency market data collection, whale-tracking, and trading signal platform with a new reinforcement-learning loop for live signal tuning.

## Projects

### [market-scraper](market-scraper/)
Real-time cryptocurrency market data collection system for Hyperliquid.

- Event-driven architecture with WebSocket data collection
- Trader scoring and position tracking
- Signal generation (BUY/SELL/NEUTRAL)
- Bitcoin on-chain metrics (CBBI, Fear & Greed, MVRV, SOPR, NUPL)
- REST API + WebSocket streaming (port 3845)

### [smart-money-signal-system](smart-money-signal-system/)
Real-time trading signal generation from whale position tracking.

- Subscribes to Redis events from market-scraper
- Whale alert detection with priority levels
- Multi-dimensional trader weighting engine
- ML-based market regime detection
- RL outcome tracking, checkpoint loading, and offline retraining
- REST API (port 4341)

### [data-sources](data-sources/)
API documentation and scripts for cryptocurrency data providers.

| Source | Description |
|--------|-------------|
| [hyperliquid](data-sources/hyperliquid/) | DEX trading data, vaults, funding rates |
| [cbbi](data-sources/cbbi/) | Bitcoin Bull Run Index (MVRV Z-Score, Reserve Risk) |
| [cryptoquant](data-sources/cryptoquant/) | On-chain analytics, exchange flows |
| [bitcoinmagazinepro](data-sources/bitcoinmagazinepro/) | Fear & Greed Index, Puell Multiple |

## Architecture

```
┌─────────────────┐     Redis Pub/Sub     ┌──────────────────────────┐
│ market-scraper  │ ────────────────────► │ smart-money-signal-system│
│                 │                       │                          │
│ - Collectors    │ trader_positions      │ - Whale Detector         │
│ - Processors    │ scored_traders        │ - Signal Generator       │
│ - On-chain      │ candles               │ - Regime Detection       │
│                 │ mark_price            │ - Outcome Tracker        │
│  :3845 API      │                       │ - RL Param Server        │
│  :3845 WS       │                       │ - Retraining API         │
└─────────────────┘                       └──────────────────────────┘
        │                                             │
        ▼                                             ▼
   MongoDB                                      MongoDB + checkpoints
   market_scraper                               signal_system / `checkpoints/`
```

### Data Flow

1. **market-scraper** collects trader positions, candles, and mark prices → publishes to Redis
2. **smart-money-signal-system** subscribes to those events
3. Signal generation produces BUY/SELL/NEUTRAL outputs using trader bias plus RL-tuned thresholds
4. Mark-price events resolve historical outcomes and persist them for RL training
5. Offline retraining writes checkpoints that are loaded on startup or pushed via API

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Redis
- uv package manager

### Option 1: Quick Start (Development)

Start both servers with a single command:

```bash
# Start both servers in background
./scripts/start-all.sh --background

# Check status
./scripts/status.sh

# View logs
tail -f logs/market-scraper.log
tail -f logs/signal-system.log

# Stop all servers
./scripts/stop-all.sh
```

### Option 2: Manual Start

```bash
# Terminal 1 - market-scraper
cd market-scraper
uv sync
uv run python -m market_scraper server

# Terminal 2 - signal-system
cd smart-money-signal-system
uv sync
uv run python -m signal_system server
```

### Option 3: Production (systemd)

```bash
# Install systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable market-scraper.service signal-system.service
sudo systemctl start market-scraper.service

# Check status
sudo systemctl status market-scraper.service signal-system.service
```

See [systemd/README.md](systemd/README.md) for detailed instructions.

## Technologies

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| Package Manager | uv |
| Web Framework | FastAPI |
| Database | MongoDB |
| Cache/PubSub | Redis |
| HTTP Client | aiohttp, httpx |
| Data Processing | pandas, numpy |
| Machine Learning | scikit-learn, Gymnasium, PyTorch |
| Validation | pydantic |
| Logging | structlog |
| Testing | pytest |

## Project Structure

```
cryptoOS/
├── market-scraper/              # Market data collection
│   ├── src/market_scraper/      # Main source code
│   ├── scripts/                 # Utility scripts
│   ├── tests/                   # Test suite
│   └── docs/                    # Documentation
├── smart-money-signal-system/   # Signal generation + RL tuning
│   ├── src/signal_system/       # Main source code
│   ├── checkpoints/             # RL checkpoints (generated)
│   └── tests/                   # Test suite
├── docs/                        # Plans and reports
├── data-sources/                # API documentation
├── scripts/                     # Deployment scripts
│   ├── start-all.sh             # Start all servers
│   ├── stop-all.sh              # Stop all servers
│   └── status.sh                # Check server status
└── systemd/                     # Production services
    ├── market-scraper.service   # systemd unit file
    └── signal-system.service    # systemd unit file
```

## Documentation

| Document | Description |
|----------|-------------|
| [market-scraper/README.md](market-scraper/README.md) | Market scraper features and API |
| [smart-money-signal-system/README.md](smart-money-signal-system/README.md) | Signal system, RL flow, and API |
| [docs/README.md](docs/README.md) | Top-level docs inventory and archival policy |
| [systemd/README.md](systemd/README.md) | Production deployment with systemd |
| [docs/reports/2026-04-26-recent-changes-report.md](docs/reports/2026-04-26-recent-changes-report.md) | Detailed report on the recent RL changes |
| [market-scraper/docs/guides/deployment.md](market-scraper/docs/guides/deployment.md) | Detailed deployment guide |

## License

MIT
