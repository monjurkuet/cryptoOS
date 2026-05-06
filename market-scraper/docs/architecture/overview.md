# Architecture Overview

## System Architecture

The Market Scraper Framework follows an event-driven, hexagonal (ports and adapters) architecture that promotes loose coupling, testability, and extensibility.

## Component Diagram

```
 ┌─────────────────────────────────────────────────────────┐
 │ External Clients                                       │
 │ ┌──────────┐ ┌──────────────┐ ┌────────────────┐      │
 │ │ REST     │ │ WebSocket    │ │ Connectors     │      │
 │ │ Clients  │ │ Subscribers  │ │ (Data Sources) │      │
 │ └────┬─────┘ └──────┬───────┘ └───────┬────────┘      │
 └───────┼───────────────┼──────────────────┼─────────────┘
         │               │                  │
 ┌───────▼───────────────▼──────────────────▼─────────────┐
 │ API Layer                                              │
 │ ┌─────────────────────────────────────────────────┐   │
 │ │ FastAPI Server (REST + WebSocket)               │   │
 │ │ - /health, /api/v1/markets, /api/v1/traders     │   │
 │ │ - /api/v1/signals, /api/v1/cbbi, /api/v1/onchain│   │
 │ │ - /ws (WebSocket streaming)                     │   │
 │ └─────────────────────────────────────────────────┘   │
 └───────────────────────────┬─────────────────────────────┘
                             │
 ┌───────────────────────────▼─────────────────────────────┐
 │ Core Application                                       │
 │                                                        │
 │ ┌────────────────┐ ┌───────────────┐ ┌────────────┐   │
 │ │ Orchestration  │ │ Event Bus     │ │ Processors  │   │
 │ │ - Lifecycle    │ │ (Pub/Sub)     │ │ - Position  │   │
 │ │ - Scheduler    │ │ - Redis+Local │ │ - Scoring   │   │
 │ │ - Health       │ │ - Memory      │ │ - Signals   │   │
 │ └────────┬────────┘ └───────┬───────┘ └──────┬─────┘   │
 │          │                  │                 │         │
 └──────────┼──────────────────┼─────────────────┼─────────┘
            │                  │                 │
 ┌──────────▼──────────────────▼─────────────────▼─────────┐
 │ Storage Layer                                          │
 │ ┌─────────────────┐ ┌────────────────────────┐         │
 │ │ MongoDB         │ │ Redis Cache            │         │
 │ │ (Persistence)   │ │ (Pub/Sub + In-Memory)  │         │
 │ └─────────────────┘ └────────────────────────┘         │
 └────────────────────────────────────────────────────────┘
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
│ Application Core                                            │
│ ┌───────────────────────────────────────────────────────┐  │
│ │ Domain Logic                                           │  │
│ │ - Events, Types, Business Rules                       │  │
│ └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│ ┌────────────────────────┼────────────────────────────┐   │
│ │ Ports (Interfaces)     │                            │   │
│ │ - DataConnector, DataRepository, EventBus           │   │
│ └────────────────────────┼────────────────────────────┘   │
└──────────────────────────┼─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│ Adapters (Implementations)                                 │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐│
│ │ Connectors   │ │ Storage      │ │ Event Bus            ││
│ │ - Hyperliquid│ │ - MongoDB    │ │ - Redis (remote)     ││
│ │ - CBBI       │ │ - Redis Cache│ │ - Direct (local)     ││
│ │ - CryptoQuant│ │              │ │                      ││
│ └──────────────┘ └──────────────┘ └──────────────────────┘│
└───────────────────────────────────────────────────────────┘
```

### 3. Dual Dispatch Pattern

The event bus supports two dispatch modes:
- **Direct Dispatch** (local): In-process handlers receive events immediately via `subscribe_local()`, bypassing Redis serialization. Used for storage, signal generation, and leaderboard sync.
- **Redis Pub/Sub** (remote): Events are published to Redis channels for external consumers (API server, WebSocket streaming, cross-process communication).

This hybrid approach eliminates ~190 Redis round-trips per flush cycle for internal events while maintaining compatibility with external consumers.

### 4. Write Buffering

Position data is buffered in-memory and flushed periodically (5s or 50 items) using `bulk_write` with `UpdateOne` operations. This reduces MongoDB Atlas round-trips from ~380 individual writes per flush to 1-2 batch operations.

### 5. Quick Hash Dedup

Before expensive normalization, a lightweight hash of position state (coin, size, entry price, leverage) and open orders (coin, side, size, price) is computed. If the hash matches the previous value for that trader, the update is skipped entirely — saving ~65% of CPU-intensive normalization work.

## Key Components

### Lifecycle Manager (`orchestration/lifecycle.py`)
Central orchestrator that manages startup, shutdown, and the main event loop. Key features:
- Dedicated `ThreadPoolExecutor(max_workers=4)` for MongoDB writes
- `asyncio.Semaphore(12)` to cap concurrent database operations
- Position buffer with periodic flush for batched writes
- Configurable health monitoring and memory guardian

### Trader WebSocket Collector (`connectors/hyperliquid/collectors/trader_ws.py`)
Manages multiple WebSocket connections to Hyperliquid for real-time trader data. Key features:
- Multiple `TraderWSClient` instances (one per WS connection)
- Message buffer with configurable flush interval (120s)
- Quick hash dedup before normalization
- Normalization runs in a dedicated `ThreadPoolExecutor(2)`
- Staggered reconnection with 15s backoff floor

### Redis Bus (`event_bus/redis_bus.py`)
Dual-mode event bus supporting both Redis pub/sub and direct local dispatch. Key features:
- `subscribe_local()` for in-process handlers (zero Redis overhead)
- `publish()` dispatches locally first, then to Redis
- Automatic reconnection on pub/sub failures
- `_subscribed` asyncio.Event to prevent startup race conditions

### MongoDB Repository (`storage/mongo_repository.py`)
Async-safe persistence layer with TTL indexes and bulk operations. Key features:
- `bulk_upsert_trader_states()` for batched position writes
- TTL indexes with automatic cleanup of expired data
- Connection validation via `ping` on connect
- Graceful error handling with `OperationFailure` code 85 support
