# Architecture Overview

## System Architecture

The Market Scraper Framework follows an event-driven, hexagonal (ports and adapters) architecture that promotes loose coupling, testability, and extensibility.

## Component Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    External Clients                     │
                    │  ┌──────────┐  ┌──────────────┐  ┌────────────────┐   │
                    │  │  REST    │  │  WebSocket   │  │  Connectors    │   │
                    │  │  Clients │  │  Subscribers │  │  (Data Sources)│   │
                    │  └────┬─────┘  └──────┬───────┘  └───────┬────────┘   │
                    └───────┼───────────────┼──────────────────┼─────────────┘
                            │               │                  │
                    ┌───────▼───────────────▼──────────────────▼─────────────┐
                    │                        API Layer                        │
                    │  ┌─────────────────────────────────────────────────┐   │
                    │  │  FastAPI Server (REST + WebSocket)              │   │
                    │  │  - /health, /api/v1/markets, /api/v1/traders    │   │
                    │  │  - /api/v1/signals, /api/v1/cbbi, /api/v1/onchain│   │
                    │  │  - /ws (WebSocket streaming)                    │   │
                    │  └─────────────────────────────────────────────────┘   │
                    └───────────────────────────┬─────────────────────────────┘
                                                │
                    ┌───────────────────────────▼─────────────────────────────┐
                    │                   Core Application                       │
                    │                                                              │
                    │  ┌────────────────┐  ┌───────────────┐  ┌────────────┐   │
                    │  │   Orchestration │  │  Event Bus    │  │  Processors │   │
                    │  │  - Lifecycle    │  │  (Pub/Sub)    │  │  - Market   │   │
                    │  │  - Scheduler    │  │  - Redis      │  │  - Candle   │   │
                    │  │  - Health       │  │  - Memory     │  │  - Metrics  │   │
                    │  └────────┬────────┘  └───────┬───────┘  └──────┬─────┘   │
                    │           │                   │                 │         │
                    └───────────┼───────────────────┼─────────────────┼─────────┘
                                │                   │                 │
                    ┌───────────▼───────────────────▼─────────────────▼─────────┐
                    │                     Storage Layer                          │
                    │  ┌─────────────────┐        ┌────────────────────────┐   │
                    │  │   MongoDB       │        │   Redis Cache           │   │
                    │  │  (Persistence)  │        │  (In-Memory)            │   │
                    │  └─────────────────┘        └────────────────────────┘   │
                    └──────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Event-Driven Architecture

All system components communicate through events. This provides:
- **Loose Coupling**: Components don't directly call each other
- **Scalability**: Events can be processed asynchronously
- **Extensibility**: New processors can be added without modifying connectors
- **Traceability**: Events carry correlation IDs for tracing

### 2. Hexagonal Architecture

The system follows hexagonal architecture with clear boundaries:

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Core                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Domain Logic                       │  │
│  │  - Events, Types, Business Rules                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌────────────────────────┼────────────────────────────┐   │
│  │              Ports (Interfaces)                      │   │
│  │  - DataConnector, DataRepository, EventBus          │   │
│  └────────────────────────┼────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    Adapters (Implementations)                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Connectors   │ │ Storage      │ │ Event Bus            │ │
│  │ - Hyperliquid│ │ - MongoDB    │ │ - Redis              │ │
│  │ - CBBI       │ │ - Memory     │ │ - Memory             │ │
│  │ - Blockchain │ │              │ │                      │ │
│  │ - FearGreed  │ │              │ │                      │ │
│  │ - CoinMetrics│ │              │ │                      │ │
│  │ - ChainExp.  │ │              │ │                      │ │
│  │ - ExchangeFl.│ │              │ │                      │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3. Interface Segregation

Each component exposes clear interfaces:
- `DataConnector`: For data source adapters
- `DataRepository`: For storage backends
- `EventBus`: For event distribution
- `Processor`: For event transformation

### 4. Dependency Inversion

High-level modules don't depend on low-level modules. Both depend on abstractions (interfaces).

## Technology Stack

### Core
- **Python 3.11+**: Language runtime
- **asyncio**: Asynchronous programming
- **pydantic**: Data validation and settings

### Data
- **MongoDB**: Primary data store for market data
- **Redis**: Event bus, caching, pub/sub

### API
- **FastAPI**: REST API framework
- **Uvicorn**: ASGI server
- **WebSockets**: Real-time streaming

### Observability
- **structlog**: Structured logging
- **Prometheus**: Metrics collection

### Testing
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support

## Data Flow

```
1. Connector fetches data from exchange
        │
        ▼
2. Data is parsed and converted to StandardEvent
        │
        ▼
3. Event is published to Event Bus
        │
        ├──────────────────┬──────────────────┐
        ▼                  ▼                  ▼
4. Processors subscribe  Storage saves      API can query
   and transform        the event           the event
```

## Scalability Considerations

### Horizontal Scaling
- Connectors can run in separate processes
- Event bus (Redis) supports distributed pub/sub
- Storage (MongoDB) supports sharding

### Performance
- Async I/O throughout the system
- Connection pooling for external services
- Batch operations for bulk data

### Resilience
- Health checks for all components
- Graceful degradation
- Retry logic with exponential backoff
