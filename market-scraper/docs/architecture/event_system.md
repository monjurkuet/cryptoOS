# Event System

The Market Scraper Framework uses an event-driven architecture built on an event bus pattern. This document explains the event system design, event types, and how events flow through the system.

## Event System Overview

The event system provides loose coupling between components through a publish-subscribe pattern:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Producer   │────▶│  Event Bus   │────▶│  Consumer   │
│ (Connector)  │     │  (Pub/Sub)   │     │ (Processor)  │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Event Types

The framework defines standard event types in `EventType`:

### Market Data Events

| Event Type | Description | Payload Fields |
|------------|-------------|----------------|
| `trade` | Individual trade | `symbol`, `price`, `volume`, `timestamp` |
| `ticker` | 24h ticker data | `symbol`, `price`, `volume`, `bid`, `ask` |
| `order_book` | Order book snapshot | `symbol`, `bid`, `ask`, `bid_volume`, `ask_volume` |
| `ohlcv` | OHLCV candle | `symbol`, `open`, `high`, `low`, `close`, `volume`, `timestamp` |

### System Events

| Event Type | Description |
|------------|-------------|
| `connector_status` | Connector state changes |
| `heartbeat` | Periodic health check |
| `error` | Error notifications |
| `custom` | User-defined events |

## Event Structure

All events follow the `StandardEvent` structure:

```python
from market_scraper.core.events import StandardEvent, EventType, MarketDataPayload

event = StandardEvent.create(
    event_type=EventType.TRADE,
    source="hyperliquid",
    payload={
        "symbol": "BTC-USD",
        "price": 50000.00,
        "volume": 1.5,
        "timestamp": "2024-01-15T10:30:00Z"
    },
    priority=5
)
```

### Event Fields

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | str | Unique UUID for the event |
| `event_type` | EventType | Classification of the event |
| `timestamp` | datetime | When the event occurred (UTC) |
| `source` | str | Origin of the event (connector name) |
| `payload` | dict | Event-specific data |
| `correlation_id` | str | For tracing related events |
| `parent_event_id` | str | For event chains |
| `priority` | int | 1-10, lower is higher priority |
| `processed_at` | datetime | When event was processed |
| `processing_time_ms` | float | Processing duration |

## Event Flow

```
1. Connector fetches data
         │
         ▼
2. Parse raw data into payload
         │
         ▼
3. Create StandardEvent
         │
         ▼
4. Publish to Event Bus
         │
    ┌────┴────┐
    ▼         ▼
Processor  Storage
   │         │
   ▼         (persisted)
Processed
   │
   ▼
API/Clients
```

## Event Bus Implementation

The framework provides two event bus implementations:

### Memory Event Bus

For single-process deployments:

```python
from market_scraper.event_bus import MemoryEventBus
from market_scraper.core.events import EventType

bus = MemoryEventBus()

# Subscribe to events
async def handler(event):
    print(f"Received: {event.event_type}")

await bus.subscribe(EventType.TRADE, handler)

# Publish events
await bus.publish(event)
```

### Redis Event Bus

For distributed deployments:

```python
from market_scraper.event_bus import RedisEventBus

bus = RedisEventBus(
    url="redis://localhost:6379",
    channel="market-events"
)

# Works the same as MemoryEventBus
await bus.subscribe(EventType.TRADE, handler)
await bus.publish(event)
```

## Event Processing

Processors subscribe to specific event types:

```python
from market_scraper.processors.base import Processor
from market_scraper.core.events import StandardEvent, EventType

class MyProcessor(Processor):
    async def process(self, event: StandardEvent) -> StandardEvent | None:
        if event.event_type == EventType.TRADE:
            # Process trade event
            return event
        return None  # Filter out other types

processor = MyProcessor(event_bus)
await processor.start()
```

## Example Events

### Trade Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "trade",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "hyperliquid",
  "payload": {
    "symbol": "BTC-USD",
    "price": 50000.00,
    "volume": 1.5,
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001",
  "priority": 5
}
```

### OHLCV Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440002",
  "event_type": "ohlcv",
  "timestamp": "2024-01-15T10:00:00Z",
  "source": "hyperliquid",
  "payload": {
    "symbol": "BTC-USD",
    "open": 49500.00,
    "high": 50200.00,
    "low": 49300.00,
    "close": 50000.00,
    "volume": 1250.5,
    "timestamp": "2024-01-15T10:00:00Z"
  },
  "priority": 5
}
```

### Error Event

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440003",
  "event_type": "error",
  "timestamp": "2024-01-15T10:30:00Z",
  "source": "hyperliquid",
  "payload": {
    "error_code": "RATE_LIMIT",
    "message": "Rate limit exceeded",
    "details": {}
  },
  "priority": 1
}
```

## Best Practices

1. **Use correlation IDs**: Link related events for tracing
2. **Set appropriate priorities**: Critical events (errors) should have priority 1
3. **Handle processing time**: Use `mark_processed()` for monitoring
4. **Filter events**: Processors should return `None` to filter out unwanted events
5. **Log events**: Use structured logging for event debugging
