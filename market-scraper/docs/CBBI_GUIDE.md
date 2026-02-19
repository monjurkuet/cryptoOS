# CBBI (Colin Talks Crypto Bitcoin Bull Run Index) Documentation

## Table of Contents

1. [Overview](#overview)
2. [What is CBBI?](#what-is-cbbi)
3. [Architecture](#architecture)
4. [Implementation Details](#implementation-details)
5. [API Reference](#api-reference)
6. [Python Usage](#python-usage)
7. [Component Reference](#component-reference)
8. [Configuration](#configuration)
9. [Interpreting the Data](#interpreting-the-data)
10. [Troubleshooting](#troubleshooting)

---

## Overview

CBBI (Colin Talks Crypto Bitcoin Bull Run Index) is a Bitcoin sentiment indicator that aggregates multiple on-chain and market metrics into a single confidence score. The market-scraper framework includes a fully implemented CBBI connector that fetches data from the official API and exposes it through REST endpoints.

**Key Features:**
- Real-time CBBI confidence score (0-100)
- All 9 component metrics with historical data
- Automatic daily polling (CBBI updates once per day)
- REST API endpoints for easy integration
- Health monitoring and error handling

---

## What is CBBI?

### The Confidence Score

The CBBI aggregates multiple Bitcoin metrics into a single "confidence" score ranging from 0 to 100:

| Score Range | Sentiment | Market Interpretation |
|-------------|-----------|----------------------|
| 0-20 | Extreme Fear | Potential market bottom, accumulation zone |
| 20-40 | Fear | Bearish sentiment, possible buying opportunity |
| 40-60 | Neutral | Balanced market, no clear direction |
| 60-80 | Greed | Bullish sentiment, caution advised |
| 80-100 | Extreme Greed | Potential market top, profit-taking zone |

### Origin

CBBI was created by Colin Talks Crypto and is maintained at [colintalkscrypto.com/cbbi](https://colintalkscrypto.com/cbbi). The index has been tracking Bitcoin market sentiment since 2019 and has historically signaled major market tops and bottoms.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CBBI Data Flow                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  CBBI API            │
│  colintalkscrypto    │
│  /cbbi/data/         │
│  latest.json         │
└──────────┬───────────┘
           │ HTTP GET
           ▼
┌──────────────────────┐
│  CBBIClient          │  src/market_scraper/connectors/cbbi/client.py
│  - HTTP requests     │
│  - Rate limiting     │
│  - Error handling    │
└──────────┬───────────┘
           │ Raw JSON
           ▼
┌──────────────────────┐
│  CBBI Parsers        │  src/market_scraper/connectors/cbbi/parsers.py
│  - parse_index()     │
│  - parse_components()│
│  - validate_data()   │
└──────────┬───────────┘
           │ StandardEvent
           ▼
┌──────────────────────┐
│  CBBIConnector       │  src/market_scraper/connectors/cbbi/connector.py
│  - connect()         │
│  - get_current_index()│
│  - stream_realtime() │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  FastAPI Router      │  src/market_scraper/api/routes/cbbi.py
│  GET /api/v1/cbbi    │
│  GET /cbbi/components│
└──────────────────────┘
```

### File Structure

```
src/market_scraper/connectors/cbbi/
├── __init__.py           # Package exports
├── config.py             # CBBIConfig settings
├── client.py             # HTTP client implementation
├── parsers.py            # Data parsing functions
└── connector.py          # Main CBBIConnector class
```

---

## Implementation Details

### 1. Configuration (`config.py`)

```python
class CBBIConfig(ConnectorConfig):
    """CBBI connector configuration."""

    base_url: HttpUrl = "https://colintalkscrypto.com/cbbi/data"
    api_key: str | None = None  # Optional for premium features
    update_interval_seconds: int = 86400  # 24 hours (CBBI updates daily)
    historical_days: int = 365  # Days of historical data
    metrics_enabled: bool = True  # Prometheus metrics
```

**Key Configuration Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `update_interval_seconds` | 86400 | Polling interval (24 hours recommended) |
| `historical_days` | 365 | Days of historical data to fetch |
| `metrics_enabled` | True | Enable Prometheus metrics |

### 2. HTTP Client (`client.py`)

The `CBBIClient` class handles all HTTP communication:

```python
class CBBIClient:
    async def connect(self) -> None:
        """Initialize HTTP connection pool."""

    async def get_index_data(self) -> dict[str, Any]:
        """Fetch current CBBI index data."""

    async def get_historical_data(self, days: int) -> list[dict]:
        """Fetch historical CBBI data."""

    async def get_component_data(self, component: str) -> dict:
        """Fetch data for a specific component."""

    async def health_check(self) -> dict[str, Any]:
        """Check API health status."""
```

**Features:**
- Rate limiting with `asyncio.Lock`
- Automatic retry logic
- Health monitoring
- Latency tracking

### 3. Parsers (`parsers.py`)

Parsing functions convert raw API responses to `StandardEvent` objects:

```python
def parse_cbbi_index_response(data: dict, source: str = "cbbi") -> StandardEvent:
    """Parse CBBI API response into StandardEvent."""

def parse_cbbi_historical_response(data: dict, days: int = 365) -> list[StandardEvent]:
    """Parse historical data into list of events."""

def parse_cbbi_component_response(data: dict, component: str) -> StandardEvent:
    """Parse specific component data."""

def validate_cbbi_data(data: dict) -> None:
    """Validate CBBI data structure."""
```

### 4. Connector (`connector.py`)

The main `CBBIConnector` class implements the `DataConnector` interface:

```python
class CBBIConnector(DataConnector):
    async def connect(self) -> None:
        """Establish connection to CBBI API."""

    async def disconnect(self) -> None:
        """Close HTTP connections."""

    async def get_current_index(self) -> StandardEvent:
        """Get current CBBI confidence score."""

    async def get_component_breakdown(self) -> list[StandardEvent]:
        """Get all component metrics."""

    async def get_specific_component(self, component: str) -> StandardEvent:
        """Get specific component data."""

    async def stream_realtime(self, symbols: list) -> AsyncIterator[StandardEvent]:
        """Stream CBBI updates (polls every 24 hours)."""
```

---

## API Reference

### Base URL

```
http://localhost:8000/api/v1/cbbi
```

### Endpoints

#### GET /api/v1/cbbi

Get current CBBI data including confidence score and all components.

**Response:**
```json
{
    "confidence": 0.3342,
    "price": 67471.05,
    "timestamp": "2026-02-17T00:00:00",
    "components": {
        "PiCycle": 0.3516,
        "RUPL": 0.3813,
        "RHODL": 0.3642,
        "Puell": 0.6215,
        "2YMA": 0.4114,
        "MVRV": 0.186,
        "ReserveRisk": 0.248,
        "Woobull": 0.2376,
        "Trolololo": 0.2062
    }
}
```

**Example:**
```bash
curl http://localhost:8000/api/v1/cbbi | jq
```

---

#### GET /api/v1/cbbi/components

Get detailed breakdown of all CBBI components with historical data.

**Response:**
```json
[
    {
        "component_name": "PiCycle",
        "description": "Pi Cycle Top Indicator - Signals potential market cycle tops",
        "current_value": 0.3516,
        "historical": [
            {"timestamp": "2026-02-17T00:00:00", "value": 0.3516},
            {"timestamp": "2026-02-16T00:00:00", "value": 0.3546},
            ...
        ]
    },
    ...
]
```

**Example:**
```bash
curl http://localhost:8000/api/v1/cbbi/components | jq
```

---

#### GET /api/v1/cbbi/components/{component_name}

Get data for a specific component.

**Available Components:**
- `PiCycle` - Pi Cycle Top Indicator
- `RUPL` - Relative Unrealized Profit/Loss
- `RHODL` - Realized HODL Ratio
- `Puell` - Puell Multiple
- `2YMA` - 2-Year Moving Average
- `MVRV` - MVRV Z-Score
- `ReserveRisk` - Reserve Risk
- `Woobull` - Woobull Top Cap vs CVDD
- `Trolololo` - Bitcoin Trolololo

**Example:**
```bash
curl http://localhost:8000/api/v1/cbbi/components/MVRV | jq
```

**Response:**
```json
{
    "component_name": "MVRV",
    "description": "MVRV Z-Score - Market Value to Realized Value deviation",
    "current_value": 0.186,
    "historical": [...]
}
```

---

#### GET /api/v1/cbbi/health

Check CBBI connector health status.

**Response:**
```json
{
    "status": "healthy",
    "latency_ms": 4118.06,
    "message": "API responding normally"
}
```

**Status Values:**
- `healthy` - API responding normally
- `degraded` - API responding but last fetch > 2 days ago
- `unhealthy` - API not responding or error

---

## Python Usage

### Basic Usage

```python
import asyncio
from market_scraper.connectors.cbbi import CBBIConnector, CBBIConfig

async def main():
    # Create connector with default config
    config = CBBIConfig(name="cbbi")
    connector = CBBIConnector(config)

    # Connect to API
    await connector.connect()

    # Get current CBBI confidence
    event = await connector.get_current_index()
    print(f"CBBI Confidence: {event.payload['confidence']}")
    print(f"BTC Price: ${event.payload['price']:,.2f}")
    print(f"Timestamp: {event.payload['timestamp']}")

    # Access components
    for name, value in event.payload['components'].items():
        print(f"  {name}: {value}")

    # Disconnect
    await connector.disconnect()

asyncio.run(main())
```

### Get Specific Component

```python
async def get_mvrv():
    connector = CBBIConnector(CBBIConfig(name="cbbi"))
    await connector.connect()

    # Get MVRV Z-Score specifically
    event = await connector.get_specific_component("MVRV")
    print(f"MVRV: {event.payload['current_value']}")
    print(f"Description: {event.payload['description']}")

    # Historical values (last 30 days)
    for point in event.payload['historical'][:10]:
        print(f"  {point['timestamp']}: {point['value']}")

    await connector.disconnect()
```

### Stream Mode (Daily Updates)

```python
async def stream_cbbi():
    config = CBBIConfig(
        name="cbbi",
        update_interval_seconds=86400,  # 24 hours
    )
    connector = CBBIConnector(config)
    await connector.connect()

    # Stream CBBI updates (polls daily)
    async for event in connector.stream_realtime(symbols=["BTC"]):
        confidence = event.payload['confidence']
        timestamp = event.payload['timestamp']

        # Process the update
        if confidence > 0.8:
            print(f"[{timestamp}] WARNING: Extreme Greed! ({confidence})")
        elif confidence < 0.2:
            print(f"[{timestamp}] OPPORTUNITY: Extreme Fear! ({confidence})")
        else:
            print(f"[{timestamp}] CBBI: {confidence}")

    await connector.disconnect()
```

### Health Check

```python
async def check_health():
    connector = CBBIConnector(CBBIConfig(name="cbbi"))
    await connector.connect()

    health = await connector.health_check()

    if health['status'] == 'healthy':
        print(f"CBBI API healthy (latency: {health['latency_ms']:.0f}ms)")
    else:
        print(f"CBBI API unhealthy: {health['message']}")

    await connector.disconnect()
```

---

## Component Reference

### PiCycle (Pi Cycle Top Indicator)

**Description:** Uses 111-day and 350-day x2 moving averages to predict market cycle tops.

**Interpretation:**
- Higher values indicate proximity to cycle top
- Values near 1.0 suggest extreme overvaluation
- Historically accurate at calling major tops

### RUPL (Relative Unrealized Profit/Loss)

**Description:** Measures the ratio of unrealized profit to unrealized loss across all Bitcoin holders.

**Interpretation:**
- High values: Many holders in profit (potential selling pressure)
- Low values: Many holders at loss (potential accumulation)
- Useful for identifying market sentiment extremes

### RHODL (Realized HODL Ratio)

**Description:** Ratio of market cap realized HODL waves, comparing young vs old coins being spent.

**Interpretation:**
- Spikes indicate old coins moving (potential distribution)
- Low values suggest HODLing behavior
- Useful for timing market cycles

### Puell (Puell Multiple)

**Description:** Ratio of daily coin issuance value to its 365-day moving average.

**Interpretation:**
- High values: Miners selling heavily (potential top)
- Low values: Miners under pressure (potential bottom)
- Good for timing miner behavior cycles

### 2YMA (Two-Year Moving Average)

**Description:** Bitcoin price relative to its 2-year moving average.

**Interpretation:**
- Price above 2YMA: Bullish
- Price below 2YMA: Bearish / Accumulation zone
- Long-term trend indicator

### MVRV (MVRV Z-Score)

**Description:** Market Value to Realized Value ratio normalized with Z-score.

**Interpretation:**
- Values > 7: Historically signals market tops
- Values < 1: Historically signals market bottoms
- One of the most reliable on-chain metrics

### ReserveRisk

**Description:** Measures confidence of long-term holders based on spending behavior.

**Interpretation:**
- Low values: Long-term holders confident (bullish)
- High values: Long-term holders selling (bearish)
- Useful for smart money tracking

### Woobull (Top Cap vs CVDD)

**Description:** Ratio of top cap to Cumulative Value Days Destroyed.

**Interpretation:**
- Compares market cap extremes to cumulative holder behavior
- Useful for identifying cycle phases
- Developed by Willy Woo

### Trolololo (Bitcoin Trolololo)

**Description:** Historical price bands based on logarithmic regression.

**Interpretation:**
- Shows fair value bands over time
- Price above upper band: Overvalued
- Price below lower band: Undervalued
- Long-term valuation tool

---

## Configuration

### Environment Variables

No environment variables required - CBBI API is public.

### YAML Configuration

Add to your application configuration:

```yaml
# config/app_config.yaml (optional)
cbbi:
  enabled: true
  update_interval_seconds: 86400  # Daily updates
  historical_days: 365
  metrics_enabled: true
```

### Programmatic Configuration

```python
from market_scraper.connectors.cbbi import CBBIConfig

config = CBBIConfig(
    name="cbbi",
    base_url="https://colintalkscrypto.com/cbbi/data",
    update_interval_seconds=86400,  # 24 hours
    historical_days=365,
    metrics_enabled=True,
)
```

---

## Interpreting the Data

### Reading the Confidence Score

The CBBI confidence score is a weighted aggregate of all component metrics. Here's how to interpret it:

```
Confidence Score Interpretation
─────────────────────────────────────────────────────
0.00 - 0.20  │  EXTREME FEAR
             │  - Historical buying opportunities
             │  - Market sentiment very negative
             │  - Potential accumulation zone
─────────────────────────────────────────────────────
0.20 - 0.40  │  FEAR
             │  - Bearish sentiment prevails
             │  - Possible dip-buying opportunity
             │  - Watch for reversal signals
─────────────────────────────────────────────────────
0.40 - 0.60  │  NEUTRAL
             │  - Balanced market conditions
             │  - No strong directional bias
             │  - Wait for clearer signals
─────────────────────────────────────────────────────
0.60 - 0.80  │  GREED
             │  - Bullish sentiment prevails
             │  - Consider taking profits
             │  - Watch for exhaustion signals
─────────────────────────────────────────────────────
0.80 - 1.00  │  EXTREME GREED
             │  - Historical selling opportunities
             │  - Market sentiment very positive
             │  - Potential distribution zone
─────────────────────────────────────────────────────
```

### Combining with Other Data

For best results, combine CBBI with:

1. **Price Action**: Look for confirmation from technical analysis
2. **Volume**: High volume confirms moves
3. **On-chain Data**: Active addresses, exchange flows
4. **Macro Context**: Interest rates, regulatory news

### Historical Accuracy

CBBI has historically identified:

| Date | CBBI Signal | Market Outcome |
|------|-------------|----------------|
| Dec 2017 | >0.95 (Top) | Bitcoin peaked at $20K |
| Dec 2018 | <0.10 (Bottom) | Bitcoin bottomed at $3K |
| Apr 2021 | >0.90 (Top) | Bitcoin peaked at $64K |
| Nov 2022 | <0.20 (Bottom) | Bitcoin bottomed at $15.5K |

---

## Troubleshooting

### Common Issues

#### 1. Connection Timeout

**Symptom:** `Failed to fetch CBBI data: Timeout`

**Solution:** The CBBI API can be slow. Default timeout is 30 seconds.

```python
# Increase timeout
config = CBBIConfig(name="cbbi")
connector = CBBIConnector(config)
connector._client = CBBIClient(config)
connector._client._client = httpx.AsyncClient(timeout=60.0)
```

#### 2. Missing Component Data

**Symptom:** `Component 'XXX' not found in data`

**Solution:** Check component names match the API:

```python
# Correct names:
"PiCycle"      # NOT "PiCycleTop"
"2YMA"         # NOT "TwoYearMA"
```

#### 3. Stale Data

**Symptom:** CBBI data not updating

**Solution:** CBBI updates once daily. Check the timestamp in the response:

```json
{
    "timestamp": "2026-02-17T00:00:00",
    ...
}
```

If timestamp is > 2 days old, check:
- API connectivity
- Health endpoint: `GET /api/v1/cbbi/health`

### Health Check Commands

```bash
# Check API health
curl http://localhost:8000/api/v1/cbbi/health

# Check data freshness
curl -s http://localhost:8000/api/v1/cbbi | jq '.timestamp'

# Check component availability
curl -s http://localhost:8000/api/v1/cbbi/components | jq 'length'
```

### Logging

Enable debug logging to see CBBI operations:

```python
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(0)  # DEBUG level
)
```

Log messages you'll see:
- `cbbi_client_connected` - Client initialized
- `cbbi_data_fetched` - Data retrieved successfully
- `cbbi_index_fetched` - Index parsed successfully
- `cbbi_components_fetched` - Components retrieved

---

## Best Practices

1. **Cache Results**: CBBI updates daily, cache responses for 24 hours
2. **Handle Errors Gracefully**: API may be temporarily unavailable
3. **Use Health Checks**: Monitor connector health in production
4. **Don't Over-poll**: Respect the 24-hour update cycle
5. **Combine Indicators**: Use CBBI alongside other metrics for confirmation

---

## References

- [CBBI Official Website](https://colintalkscrypto.com/cbbi)
- [CBBI Methodology](https://colintalkscrypto.com/cbbi-methodology)
- [Colin Talks Crypto YouTube](https://youtube.com/@ColinTalksCrypto)

---

*Last Updated: February 2026*
*Version: 1.0*
