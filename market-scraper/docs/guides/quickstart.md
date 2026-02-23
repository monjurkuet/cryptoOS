# Quick Start Guide

Get up and running with the Market Scraper Framework in 5 minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed
- **UV package manager** installed
- **MongoDB** running (local or remote)
- **Redis** (optional, for distributed event bus)

Check your versions:

```bash
python --version
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

Edit `.env` with your settings:

```bash
# MongoDB connection (required)
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper

# Redis connection (optional)
REDIS__URL=redis://localhost:6379/0

# Hyperliquid settings
HYPERLIQUID__SYMBOL=BTC
```

## Running the Application

### Start the Server

```bash
# Using the run script (recommended)
./run_server.sh start

# Or directly with uv
uv run python -m market_scraper server

# Run in foreground for development
./run_server.sh run
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Server Management

```bash
# Check status
./run_server.sh status

# View logs
tail -f server.log

# Stop server
./run_server.sh stop

# Restart server
./run_server.sh restart
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
const ws = new WebSocket('ws://localhost:8000/ws?channel=traders');

ws.onopen = () => {
    console.log('Connected to trader data stream');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Event:', data.event_type, data.payload);
};
```

Available channels:
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

If port 8000 is in use, set a different port:

```bash
SERVER_PORT=8001 ./run_server.sh start
```

### MongoDB Connection Failed

Ensure MongoDB is running:

```bash
# Check MongoDB status
mongosh --eval "db.adminCommand('ping')"

# Start MongoDB (if using local install)
sudo systemctl start mongod
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
