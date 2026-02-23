# Documentation Index

Complete documentation for the Market Scraper v2 system.

## Quick Links

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Project overview, quick start, and features |
| [DATA_STORAGE.md](docs/DATA_STORAGE.md) | MongoDB collections, schemas, and retention |
| [AGENTS.md](AGENTS.md) | AI agent development guidelines |

---

## Architecture

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/architecture/overview.md) | System design, layers, and patterns |
| [Connector Architecture](docs/architecture/connectors.md) | Data connector framework and implementations |
| [Event System](docs/architecture/event_system.md) | Event-driven architecture and event bus |

---

## Guides

| Document | Description |
|----------|-------------|
| [Quick Start](docs/guides/quickstart.md) | Get up and running in minutes |
| [Development Guide](docs/guides/development.md) | Testing, contributing, and development setup |
| [Deployment Guide](docs/guides/deployment.md) | Production deployment strategies |

---

## Feature Documentation

| Document | Description |
|----------|-------------|
| [Market Data API](docs/MARKET_DATA_API.md) | Price and historical candle endpoints |
| [CBBI Guide](docs/CBBI_GUIDE.md) | Bitcoin Bull Run Index integration |
| [Trader Filter Guide](docs/TRADER_FILTER_GUIDES.md) | Trader scoring and filter configurations |
| [Verified APIs](docs/VERIFIED_APIS.md) | External API documentation and status |

---

## API Reference

Interactive API documentation available at runtime:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### REST Endpoints Summary

| Category | Base Path | Description |
|----------|-----------|-------------|
| Health | `/health` | System health checks |
| Markets | `/api/v1/markets` | Market data and history |
| Traders | `/api/v1/traders` | Trader tracking and positions |
| Signals | `/api/v1/signals` | Trading signals |
| Connectors | `/api/v1/connectors` | Connector management |
| CBBI | `/api/v1/cbbi` | Bitcoin Bull Run Index |
| On-Chain | `/api/v1/onchain` | Bitcoin on-chain metrics |

### WebSocket Endpoints

| Channel | Endpoint | Description |
|---------|----------|-------------|
| Traders | `/ws?channel=traders` | Position and score updates |
| Signals | `/ws?channel=signals` | Trading signal alerts |

---

## Data Models

### Events

| Collection | Description |
|------------|-------------|
| `events` | Catch-all audit log (7-day retention) |

### Market Data

| Collection | Pattern | Description |
|------------|---------|-------------|
| `{symbol}_candles_{interval}` | `btc_candles_1m` | OHLCV candles |

### Trader Data

| Collection | Description |
|------------|-------------|
| `tracked_traders` | Currently tracked traders |
| `trader_positions` | Position snapshots |
| `trader_scores` | Score history |
| `trader_current_state` | Current state cache |

### Signal Data

| Collection | Description |
|------------|-------------|
| `signals` | Aggregated signals |
| `trader_signals` | Individual trader signals |

See [DATA_STORAGE.md](docs/DATA_STORAGE.md) for complete schema details.

---

## Configuration

### Environment Variables

```bash
# MongoDB
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper

# Redis (default when available)
REDIS__URL=redis://localhost:6379

# Hyperliquid
HYPERLIQUID__SYMBOL=BTC

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### YAML Configuration

Advanced settings are configured via `config/market_config.yaml`:

| Section | Description |
|---------|-------------|
| `scoring` | Trader scoring weights and multipliers |
| `filters` | Trader filtering (min_score, max_count) |
| `tags` | Trader tag thresholds |
| `position_inference` | Position inference thresholds |
| `storage` | Data retention settings |
| `buffer` | Event buffering configuration |
| `candle_backfill` | Historical data backfill settings |
| `scheduler` | Periodic background task configuration |

### Scheduler Tasks

| Task | Default Interval | Description |
|------|------------------|--------------|
| `leaderboard_refresh` | 3600s (1 hour) | Refresh trader leaderboard |
| `health_check` | 600s (10 min) | System health monitoring |
| `connector_health` | 600s (10 min) | On-chain connector health |
| `data_cleanup` | disabled | Data cleanup (use TTL indexes) |

See [Trader Filter Guide](docs/TRADER_FILTER_GUIDES.md) for complete configuration options.

---

## Development

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# With coverage
uv run pytest --cov=src/market_scraper
```

### Code Structure

```
src/market_scraper/
├── api/              # REST API routes
├── collectors/       # Data collectors
├── connectors/       # External data connectors
├── core/             # Core types and events
├── processors/       # Data processors
├── storage/          # MongoDB repository
└── streaming/        # WebSocket server
```

---

## Input Validation

The API enforces strict input validation:

### Ethereum Addresses
- Must match pattern: `^0x[a-fA-F0-9]{40}$`
- Example: `0x6859da14835424957a1e6b397d8026b1d9ff7e1e`
- Invalid format returns HTTP 400 with descriptive error

### MongoDB ObjectIds
- Must be 24-character hexadecimal string
- Example: `507f1f77bcf86cd799439011`
- Invalid format returns HTTP 400 with descriptive error

---

## Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **API Status**: Check `/health/status` endpoint

---

*Last Updated: February 2026*
