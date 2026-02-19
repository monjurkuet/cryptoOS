# Connector Architecture

The Market Scraper Framework uses a connector pattern to integrate with different cryptocurrency exchanges and data sources. This document explains how connectors work and how to add new ones.

## Connector Interface

All connectors must implement the `DataConnector` abstract base class:

```python
from market_scraper.connectors.base import DataConnector, ConnectorConfig

class MyConnector(DataConnector):
    async def connect(self) -> None:
        """Establish connection to data source."""
        pass

    async def disconnect(self) -> None:
        """Gracefully close connection."""
        pass

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical market data."""
        pass

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time market data."""
        pass

    async def health_check(self) -> dict[str, Any]:
        """Check connector health."""
        pass
```

## Connector Configuration

Each connector requires a configuration object:

```python
from market_scraper.connectors.base import ConnectorConfig

config = ConnectorConfig(
    name="my_connector",
    enabled=True,
    rate_limit_per_second=10.0,
    timeout_seconds=30.0,
    max_retries=3,
    retry_delay_seconds=1.0,
)
```

### Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str | Required | Unique connector identifier |
| `enabled` | bool | true | Whether connector is active |
| `rate_limit_per_second` | float | 10.0 | API rate limit |
| `timeout_seconds` | float | 30.0 | Request timeout |
| `max_retries` | int | 3 | Maximum retry attempts |
| `retry_delay_seconds` | float | 1.0 | Delay between retries |

## Connector Structure

A typical connector implementation follows this structure:

```
connectors/my_connector/
├── __init__.py          # Package initialization
├── config.py            # Connector-specific configuration
├── client.py            # HTTP client implementation
├── parser.py            # Response parsing
└── connector.py         # Main connector class
```

### Example: Minimal Connector

```python
# connectors/my_connector/connector.py

from datetime import datetime
from typing import Any

from market_scraper.connectors.base import DataConnector, ConnectorConfig
from market_scraper.core.events import StandardEvent, EventType
from market_scraper.core.types import Symbol, Timeframe


class MyConnector(DataConnector):
    """My custom exchange connector."""

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._client = None

    async def connect(self) -> None:
        """Initialize the connector."""
        self._client = MyClient()
        await self._client.connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
        self._connected = False

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical OHLCV data."""
        # Fetch data from API
        raw_data = await self._client.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )

        # Parse into StandardEvents
        events = []
        for item in raw_data:
            event = StandardEvent.create(
                event_type=EventType.OHLCV,
                source=self.name,
                payload={
                    "symbol": symbol,
                    "open": item["open"],
                    "high": item["high"],
                    "low": item["low"],
                    "close": item["close"],
                    "volume": item["volume"],
                    "timestamp": item["timestamp"],
                },
            )
            events.append(event)

        return events

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time trades."""
        await self._client.subscribe(symbols)

        async for data in self._client.listen():
            yield StandardEvent.create(
                event_type=EventType.TRADE,
                source=self.name,
                payload={
                    "symbol": data["symbol"],
                    "price": data["price"],
                    "volume": data["volume"],
                    "timestamp": data["timestamp"],
                },
            )

    async def health_check(self) -> dict[str, Any]:
        """Check if connector is healthy."""
        try:
            latency = await self._client.ping()
            return {
                "status": "healthy" if latency < 1000 else "degraded",
                "latency_ms": latency,
                "message": "OK",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e),
            }
```

## Registering Connectors

Connectors are registered with the `ConnectorRegistry`:

```python
from market_scraper.connectors.registry import ConnectorRegistry

registry = ConnectorRegistry()

# Register your connector
registry.register("my_connector", MyConnector)

# Get a connector instance
connector = await registry.get_connector("my_connector")
```

## Connector Registry

The registry provides a factory pattern for connector management:

```python
# List available connectors
connectors = registry.list_connectors()

# Check if connector exists
if registry.has_connector("my_connector"):
    ...

# Get connector config
config = await registry.get_config("my_connector")
```

## Best Practices

1. **Implement all abstract methods**: Even if not used, provide stub implementations
2. **Use async context managers**: Implement `__aenter__` and `__aexit__` for clean resource management
3. **Handle errors gracefully**: Return proper health check status on failures
4. **Respect rate limits**: Use the configured rate limiting
5. **Parse data correctly**: Convert exchange-specific formats to StandardEvent
6. **Log appropriately**: Use structured logging for debugging
7. **Test thoroughly**: Include unit and integration tests

## Existing Connectors

The framework includes these connectors:

### Hyperliquid

Decentralized perpetual futures exchange with real-time market data:
- **Trades**: Real-time trade feed with WebSocket
- **Orderbook**: Live orderbook updates
- **Candles**: OHLCV candle aggregation
- **Trader Data**: Position tracking for top traders

### CBBI (Colin Talks Crypto Bitcoin Bull Run Index)

Bitcoin sentiment index that aggregates multiple on-chain and market metrics:
- **Confidence Score**: 0-100 sentiment indicator
- **Components**: Pi Cycle Top, RUPL, RHODL, Puell Multiple, Two Year MA, MVRV Z-Score, Reserve Risk, Woobull
- **Update Frequency**: Daily (polls every 24 hours by default)
- **API Endpoint**: `https://colintalkscrypto.com/cbbi/data/latest.json`

```python
# Example CBBI usage
from market_scraper.connectors.cbbi import CBBIConnector, CBBIConfig

async def get_btc_sentiment():
    connector = CBBIConnector(CBBIConfig(name="cbbi"))
    await connector.connect()

    # Get current CBBI confidence score
    event = await connector.get_current_index()
    print(f"CBBI Confidence: {event.payload['confidence']}")
    print(f"Components: {event.payload['components']}")

    await connector.disconnect()
```

### BlockchainInfo

Bitcoin network metrics from Blockchain.info:
- **Hash Rate**: Network hash rate in GH/s
- **Difficulty**: Mining difficulty
- **Block Height**: Current block height
- **Total BTC**: Circulating supply
- **Price**: 24-hour average price

```python
from market_scraper.connectors.blockchain_info import BlockchainInfoConnector, BlockchainInfoConfig

async def get_network_metrics():
    connector = BlockchainInfoConnector(BlockchainInfoConfig(name="blockchain_info"))
    await connector.connect()

    event = await connector.get_current_metrics()
    print(f"Block Height: {event.payload['block_height']}")
    print(f"Hash Rate: {event.payload['hash_rate_ghs']} GH/s")

    await connector.disconnect()
```

### FearGreed

Crypto Fear & Greed Index from Alternative.me:
- **Value**: Index value (0-100)
- **Classification**: Sentiment label (Extreme Fear to Extreme Greed)
- **Historical**: Historical index values

```python
from market_scraper.connectors.fear_greed import FearGreedConnector, FearGreedConfig

async def get_sentiment():
    connector = FearGreedConnector(FearGreedConfig(name="fear_greed"))
    await connector.connect()

    event = await connector.get_current_index()
    print(f"Fear & Greed: {event.payload['value']} ({event.payload['classification']})")

    await connector.disconnect()
```

### CoinMetrics

Bitcoin metrics from Coin Metrics Community API:
- **PriceUSD**: Current price in USD
- **CapMrktCurUSD**: Market capitalization
- **AdrActCnt**: Daily active addresses
- **TxCnt**: Daily transaction count
- **SplyCur**: Current circulating supply

```python
from market_scraper.connectors.coin_metrics import CoinMetricsConnector, CoinMetricsConfig

async def get_metrics():
    connector = CoinMetricsConnector(CoinMetricsConfig(name="coin_metrics"))
    await connector.connect()

    event = await connector.get_latest_metrics()
    print(f"Price: ${event.payload['metrics']['PriceUSD']}")
    print(f"Active Addresses: {event.payload['metrics']['AdrActCnt']}")

    await connector.disconnect()
```

### ChainExposed

Bitcoin on-chain metrics from ChainExposed:
- **SOPR**: Spent Output Profit Ratio
- **NUPL**: Net Unrealized Profit/Loss
- **MVRV**: Market Value to Realized Value
- **Dormancy**: Average age of spent coins

```python
from market_scraper.connectors.chainexposed import ChainExposedConnector, ChainExposedConfig

async def get_sopr():
    connector = ChainExposedConnector(ChainExposedConfig(name="chainexposed"))
    await connector.connect()

    event = await connector.get_sopr()
    print(f"SOPR: {event.payload['value']}")
    print(f"Interpretation: {event.payload['interpretation']}")

    await connector.disconnect()
```

### ExchangeFlow

Bitcoin exchange flow metrics from Coin Metrics CSV data:
- **Flow In**: BTC flowing into exchanges
- **Flow Out**: BTC flowing out of exchanges
- **Netflow**: Net flow (outflow - inflow)
- **Supply**: Total BTC on exchanges

```python
from market_scraper.connectors.exchange_flow import ExchangeFlowConnector, ExchangeFlowConfig

async def get_flows():
    connector = ExchangeFlowConnector(ExchangeFlowConfig(name="exchange_flow"))
    await connector.connect()

    event = await connector.get_current_flows()
    print(f"Netflow: {event.payload['netflow_btc']} BTC")
    print(f"Signal: {event.payload['netflow_interpretation']}")

    await connector.disconnect()
```

## Unified On-Chain API

All on-chain connectors are aggregated through the `/api/v1/onchain` endpoints:

```bash
# Get unified summary
curl http://localhost:8000/api/v1/onchain/btc/summary

# Get specific metrics
curl http://localhost:8000/api/v1/onchain/btc/network
curl http://localhost:8000/api/v1/onchain/btc/sentiment
curl http://localhost:8000/api/v1/onchain/btc/sopr
```

See `src/market_scraper/connectors/` for implementation examples.
