# Quick Start Guide

Get up and running with the Market Scraper Framework in 5 minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **Docker and Docker Compose** installed
- **UV package manager** installed

Check your versions:

```bash
python --version
docker --version
uv --version
```

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd market-scraper
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Configure Environment

Copy the environment template:

```bash
cp .env.example .env
```

The default settings should work for local development. The `.env` file contains:

```bash
# Redis connection
REDIS__URL=redis://localhost:6379

# MongoDB connection
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper

# Application
APP_NAME=market-scraper
DEBUG=false
```

### 4. Start Services

Start Redis and MongoDB using Docker Compose:

```bash
docker-compose up -d
```

Verify services are running:

```bash
docker-compose ps
```

Expected output:
```
NAME                     IMAGE          COMMAND              STATUS
market-scraper-redis     redis:7-alpine "redis-server..."    Up
market-scraper-mongodb   mongo:7        "docker-entrypoint..." Up
```

## Running the Application

### Option 1: Run the API Server

```bash
uv run uvicorn market_scraper.api:app --reload
```

The API will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Option 2: Run as Application

```bash
uv run python -m market_scraper
```

### Option 3: Use the CLI

```bash
market-scraper
```

## First Data Fetch

### Using the REST API

```bash
# Check health
curl http://localhost:8000/health/live

# List available connectors
curl http://localhost:8000/api/v1/connectors

# Query market data
curl "http://localhost:8000/api/v1/markets/BTC-USD"

# Get current trading signal
curl http://localhost:8000/api/v1/signals/current

# Get Bitcoin on-chain metrics
curl http://localhost:8000/api/v1/onchain/btc/summary

# Get CBBI confidence score
curl http://localhost:8000/api/v1/cbbi

# Get Fear & Greed Index
curl http://localhost:8000/api/v1/onchain/btc/sentiment
```

### Using Python

```python
import asyncio
from datetime import datetime, timedelta
from market_scraper.connectors.hyperliquid import HyperliquidConnector, HyperliquidConfig

async def main():
    # Create connector
    config = HyperliquidConfig(name="hyperliquid")
    connector = HyperliquidConnector(config)

    # Connect
    await connector.connect()

    # Fetch historical data
    events = await connector.get_historical_data(
        symbol="BTC",
        timeframe="1h",
        start=datetime.now() - timedelta(days=1),
        end=datetime.now(),
    )

    print(f"Fetched {len(events)} events")
    for event in events[:3]:
        print(f"  {event.event_type}: {event.payload}")

    await connector.disconnect()

asyncio.run(main())
```

### Using WebSocket Streaming

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws?channel=market');

ws.onopen = () => {
    console.log('Connected to market data stream');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Event:', data.event_type, data.payload);
};
```

Available channels:
- `market` - Trade and orderbook updates
- `traders` - Trader position and score updates
- `signals` - Trading signal alerts

## Running Tests

Verify your installation with the test suite:

```bash
# Run all tests
pytest

# Run specific test types
pytest -m unit
pytest -m integration
pytest -m e2e

# Run with coverage
pytest --cov=src/market_scraper
```

## Common Issues

### Port Already in Use

If port 8000 is in use, specify a different port:

```bash
uv run uvicorn market_scraper.api:app --port 8001
```

### Connection Refused

Ensure Docker services are running:

```bash
docker-compose restart
```

### Import Errors

Make sure you're using the virtual environment:

```bash
source .venv/bin/activate
# or
uv run <command>
```

## Next Steps

Now that you have the framework running:

1. Read the [Architecture Overview](../architecture/overview.md) to understand the system
2. Check out the [Development Guide](../guides/development.md) for testing
3. Explore the [Deployment Guide](../guides/deployment.md) for production setup
4. Review the [API Documentation](http://localhost:8000/docs)
