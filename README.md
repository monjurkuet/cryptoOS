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
        │
        ▼
   MongoDB
```

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Redis
- uv package manager

### Run market-scraper

```bash
cd market-scraper
uv sync
cp .env.example .env
# Edit .env with MongoDB/Redis URLs
uv run python -m market_scraper server
```

### Run signal-system

```bash
cd smart-money-signal-system
uv sync
cp .env.example .env
# Edit .env with Redis URL
uv run python -m signal_system
```

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

## License

MIT
