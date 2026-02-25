# CryptoData

Cryptocurrency market data collection and trading signal generation platform.

## Projects

### [market-scraper](market-scraper/)
Real-time cryptocurrency market data collection system for Hyperliquid.

- Event-driven architecture with WebSocket data collection
- Trader scoring and position tracking
- Signal generation (BUY/SELL/NEUTRAL)
- Bitcoin on-chain metrics (CBBI, Fear & Greed, MVRV, SOPR, NUPL)
- REST API + WebSocket streaming (port 8000)

### [smart-money-signal-system](smart-money-signal-system/)
Real-time trading signal generation from whale position tracking.

- Subscribes to Redis events from market-scraper
- Whale alert detection with priority levels
- Multi-dimensional trader weighting engine
- ML-based market regime detection
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
┌─────────────────┐     Redis Pub/Sub     ┌─────────────────────┐
│ market-scraper  │ ────────────────────► │ signal-system       │
│                 │                       │                     │
│ - Collectors    │  events:positions     │ - Whale Detector    │
│ - Processors    │  events:scored        │ - Weighting Engine  │
│ - On-chain      │  events:candles       │ - Signal Generator  │
│                 │                       │ - ML Regime Detect  │
│  :8000 API      │                       │  :4341 API          │
│  :8000 WS       │                       │                     │
└─────────────────┘                       └─────────────────────┘
        │                                         │
        ▼                                         ▼
   MongoDB                                   SignalStore
   (signals collection)                     (in-memory cache)
```

### Data Flow

1. **market-scraper** collects trader positions → publishes to Redis
2. **signal-system** subscribes to Redis events
3. **signal-system** generates signals → stores in SignalStore + publishes back to Redis
4. **market-scraper** receives signals → saves to MongoDB `signals` collection
5. Both APIs serve data from their respective storage

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
| Language | Python 3.10+ |
| Package Manager | uv |
| Web Framework | FastAPI |
| Database | MongoDB (Motor) |
| Cache/PubSub | Redis |
| HTTP Client | aiohttp, httpx |
| Data Processing | pandas, numpy |
| Machine Learning | scikit-learn |
| Validation | pydantic |
| Logging | structlog |
| Testing | pytest |

## Project Structure

```
cryptodata/
├── market-scraper/              # Market data collection
│   ├── src/market_scraper/      # Main source code
│   ├── scripts/                 # Utility scripts
│   ├── tests/                   # Test suite
│   └── docs/                    # Documentation
├── smart-money-signal-system/   # Signal generation
│   ├── src/signal_system/       # Main source code
│   └── tests/                   # Test suite
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
| [smart-money-signal-system/README.md](smart-money-signal-system/README.md) | Signal system features and API |
| [systemd/README.md](systemd/README.md) | Production deployment with systemd |
| [market-scraper/docs/guides/deployment.md](market-scraper/docs/guides/deployment.md) | Detailed deployment guide |

## License

MIT
