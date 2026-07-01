# cryptoOS

Cryptocurrency market data collection, whale-tracking, and trading signal platform.

## Active Project

### [market-scraper](market-scraper/)
Real-time cryptocurrency market data collection system for Hyperliquid.

- Event-driven architecture with WebSocket data collection
- Trader scoring and position tracking
- Saved Binance.com account positions from user-provided read-only API keys
- Signal generation (BUY/SELL/NEUTRAL)
- Bitcoin on-chain metrics (CBBI, Fear & Greed, MVRV, SOPR, NUPL)
- REST API + WebSocket streaming (port 3845)
- Managed via systemd (`market-scraper.service`)

## Research / Code-Only

### [smart-money-signal-system](smart-money-signal-system/)
Trading signal generation from whale position tracking — source code and tests, **not deployed**.

- Subscribes to Redis events from market-scraper
- Whale alert detection with priority levels
- Multi-dimensional trader weighting engine
- ML-based market regime detection
- RL outcome tracking and offline retraining

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
┌─────────────────┐     Redis Pub/Sub
│ market-scraper  │ ────────────────────►  (signal-system — code only, not deployed)
│                 │
│ - Collectors    │ trader_positions
│ - Processors    │ scored_traders
│ - On-chain      │ candles
│                 │ mark_price
│  :3845 API      │
│  :3845 WS       │
└─────────────────┘
        │
        ▼
   MongoDB
   market_scraper
```

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Redis
- uv package manager

### Development

```bash
# Start market-scraper
cd market-scraper
uv sync
uv run python -m market_scraper server
```

### Production (systemd)

```bash
# Install systemd service
sudo cp systemd/market-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable market-scraper.service
sudo systemctl start market-scraper.service

# Check status
sudo systemctl status market-scraper.service
```

See [systemd/README.md](systemd/README.md) for detailed instructions.

## Verification

```bash
curl http://localhost:3845/health/live
```

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
├── market-scraper/              # Market data collection (active)
│   ├── src/market_scraper/      # Main source code
│   ├── config/                  # Configuration files
│   ├── tests/                   # Test suite (335 passed, 11 skipped)
│   └── docs/                    # Documentation
├── smart-money-signal-system/   # Signal generation + RL (code only)
│   ├── src/signal_system/       # Source code
│   └── tests/                   # Test suite
├── shared/                      # Shared Pydantic/config utilities
├── data-sources/                # Data provider API documentation
├── scripts/                     # Utility scripts
│   ├── start-market-scraper.sh  # Start market-scraper
│   ├── stop-all.sh              # Stop all servers
│   └── status.sh                # Check server status
├── systemd/                     # Production services
│   └── market-scraper.service   # systemd unit file
├── docs/                        # Documentation and reports
└── logs/                        # Runtime logs (gitignored)
```

## Documentation

| Document | Description |
|----------|-------------|
| [market-scraper/README.md](market-scraper/README.md) | Market scraper features and API |
| [docs/binance-account-positions.md](docs/binance-account-positions.md) | Saved Binance account position setup and API |
| [smart-money-signal-system/README.md](smart-money-signal-system/README.md) | Signal system, RL flow, and API |
| [docs/hybrid-compute-deployment.md](docs/hybrid-compute-deployment.md) | Current deployment status |
| [systemd/README.md](systemd/README.md) | Production deployment with systemd |
| [market-scraper/docs/guides/deployment.md](market-scraper/docs/guides/deployment.md) | Detailed deployment guide |

## License

MIT