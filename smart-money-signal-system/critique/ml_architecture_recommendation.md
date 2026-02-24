# ML Architecture Recommendation

**Date**: 2026-02-24
**Question**: Should ML features be in smart-money-signal-system or market-scraper?
**Verdict**: **SEPARATE REPOSITORIES** - ML in smart-money-signal-system

---

## Executive Summary

**Recommendation**: Keep ML components **separate** from market-scraper.

**Rationale**:
1. **Different dependency requirements** (ML libs vs scraping libs)
2. **Different deployment patterns** (GPU/CPU inference vs network I/O)
3. **Clean separation of concerns** (data infrastructure vs intelligence layer)
4. **Easier A/B testing** of ML models without touching data pipeline
5. **2026 best practice**: Feature stores and model serving are separate from data collection

---

## Architecture Comparison

### Option A: ML in market-scraper (Monolithic)

```
market-scraper/
├── connectors/          # Data collection
├── processors/          # Event processing
├── ml/                  # ML components
│   ├── feature_importance.py
│   └── regime_detection.py
└── signal_generation/   # Signals
```

**Pros**:
- Single codebase to deploy
- No inter-service communication
- Simpler initial setup

**Cons**:
- Heavy dependencies (scikit-learn, joblib) in scraper
- Harder to iterate on ML without affecting data pipeline
- Cannot scale ML independently
- Testing complexity (ML tests + scraper tests together)
- Violates single responsibility principle

---

### Option B: ML in smart-money-signal-system (Recommended)

```
market-scraper/                    smart-money-signal-system/
├── connectors/                    ├── ml/
├── processors/                    │   ├── feature_importance.py
├── signal_generation/             │   ├── regime_detection.py
└── (NO ML)                        │   └── model_registry/
                                   ├── weighting_engine/
                                   ├── whale_alerts/
                                   └── api/
```

**Data Flow**:
```
market-scraper (Data Layer)
       │
       │ Events via Redis/Memory Bus
       ▼
smart-money-signal-system (Intelligence Layer)
       │
       │ ML-weighted signals
       ▼
    Trading API / Dashboard
```

**Pros**:
- Clean separation: scraper = data, signal-system = intelligence
- Independent deployment cycles
- Can A/B test ML models without touching scraper
- Different scaling strategies (scraper = network I/O, ML = CPU/GPU)
- Easier to onboard ML engineers (don't need scraper knowledge)
- 2026 industry standard (see: Nansen, Glassnode architecture)

**Cons**:
- Two codebases to manage
- Inter-service communication (minimal with event bus)
- Slightly more complex initial setup

---

## 2026 Industry Research

### Nansen Architecture (Crypto Analytics)

**Source**: Nansen Engineering Blog (2025)

```
Data Collection Layer (Scrapers, RPC nodes)
         │
         │ Kafka/Redis Streams
         ▼
Feature Store (Offline + Online)
         │
         │
         ▼
ML Inference Layer (Smart Money signals)
         │
         │
         ▼
API / Dashboard
```

**Key Insight**: "Separating data infrastructure from intelligence layer allowed us to iterate on ML models 10x faster without breaking data pipelines."

---

### Glassnode Architecture (On-Chain Analytics)

**Source**: Glassnode State of On-Chain Analysis (2026)

```
Data Ingestion (100+ sources)
         │
         │
         ▼
Metric Computation Engine
         │
         │
         ▼
Signal Generation (ML + Rules)
         │
         │
         ▼
Client Delivery
```

**Key Insight**: "ML models are versioned and deployed independently from data collection. This allows quarterly model updates without data pipeline changes."

---

### FX24News - ML in Trading (2026)

**Source**: "How AI & Machine Learning Are Transforming Trading in 2026"

**Finding**: "Professional trading firms separate data infrastructure from signal generation. ML models are treated as separate services with their own deployment pipelines."

---

## Recommended Architecture

### Repository Structure

```
cryptodata/
├── market-scraper/              # Data Infrastructure
│   ├── connectors/              # Hyperliquid, CBBI, on-chain
│   ├── processors/              # Event processing
│   ├── event_bus/               # Redis/Memory bus
│   └── storage/                 # MongoDB, Memory
│
├── smart-money-signal-system/   # Intelligence Layer
│   ├── ml/                      # ML components
│   │   ├── feature_importance.py
│   │   ├── regime_detection.py
│   │   └── model_registry.py
│   ├── weighting_engine/        # Trader weighting
│   ├── whale_alerts/            # Alert system
│   ├── signal_generation/       # ML-enhanced signals
│   └── api/                     # Signal API
│
└── shared-events/               # Optional: Shared event schemas
    └── schemas.py
```

### Dependency Separation

**market-scraper** (pyproject.toml):
```toml
dependencies = [
    "aiohttp>=3.8.0",        # HTTP client
    "websockets>=12.0",      # WebSocket
    "motor>=3.3.0",          # MongoDB
    "redis>=5.0.0",          # Event bus
    "structlog>=23.0.0",     # Logging
    "pydantic>=2.5.0",       # Validation
    # NO ML dependencies
]
```

**smart-money-signal-system** (pyproject.toml):
```toml
dependencies = [
    # Data layer (for event consumption)
    "redis>=5.0.0",
    "pydantic>=2.5.0",
    
    # ML dependencies
    "scikit-learn>=1.4.0",
    "joblib>=1.3.0",
    "pandas>=2.0.0",
    "numpy>=1.25.0",
    
    # API
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]
```

### Communication Pattern

**Option 1: Redis Event Bus (Recommended)**

```python
# market-scraper publishes
await redis_event_bus.publish(StandardEvent(
    event_type="trader_positions",
    payload={...}
))

# smart-money-signal-system subscribes
await redis_event_bus.subscribe("trader_positions", handler)
```

**Option 2: HTTP Webhooks**

```python
# market-scraper posts to signal system
await http.post("http://localhost:4341/api/v1/events", json=event)
```

**Option 3: Shared Memory (Development only)**

```python
# Both use same MemoryEventBus instance
# Only works when running in same process
```

---

## Deployment Strategy

### Development (Single Machine)

```bash
# Terminal 1: market-scraper
cd market-scraper
uv run python -m market_scraper

# Terminal 2: smart-money-signal-system
cd smart-money-signal-system
uv run python -m smart_money_signal_system

# Both connect to same Redis event bus
```

### Production (Ubuntu Bare Metal)

```bash
# Service 1: market-scraper (systemd)
/etc/systemd/system/market-scraper.service
- Runs data collection
- Publishes to Redis

# Service 2: smart-money-signal-system (systemd)
/etc/systemd/system/smart-money-signal-system.service
- Subscribes to Redis
- Runs ML inference
- Exposes signal API

# Service 3: Redis (systemd)
/etc/systemd/system/redis.service
- Event bus for both
```

---

## ML Training vs Inference

### Critical Distinction

**Training** (Offline, Weekly/Monthly):
```python
# Runs separately, not in production pipeline
python train_feature_importance.py
python train_regime_detector.py

# Outputs: Saved models in model_registry/
models/
├── feature_importance_v1.joblib
└── regime_detector_v1.joblib
```

**Inference** (Online, Real-time):
```python
# Runs in smart-money-signal-system
model = joblib.load("models/regime_detector_v1.joblib")
regime = model.predict(current_features)
```

### Why Separate?

1. **Training is slow** (minutes to hours) - cannot block real-time signals
2. **Training needs historical data** - separate data pipeline
3. **Training can fail** - shouldn't affect production signals
4. **Model versioning** - can rollback without redeploying scraper

---

## Implementation Plan (Revised)

### Phase 1: Foundation (market-scraper)

**Goal**: Enable TraderWebSocketCollector and emit events

**Files to modify**:
- `market-scraper/connectors/hyperliquid/collectors/manager.py`
- `market-scraper/orchestration/lifecycle.py`

**Output**: `trader_positions` events on Redis bus

**Timeline**: 1-2 days

---

### Phase 2: Signal System Setup (smart-money-signal-system)

**Goal**: Create new repository with event subscription

**Files to create**:
```
smart-money-signal-system/
├── pyproject.toml
├── src/signal_system/
│   ├── __init__.py
│   ├── config.py
│   ├── event_subscriber.py    # Subscribe to market-scraper events
│   └── signal_store.py        # Store generated signals
└── tests/
```

**Timeline**: 2-3 days

---

### Phase 3: Weighting Engine (smart-money-signal-system)

**Goal**: Multi-dimensional trader weighting

**Files to create**:
```
smart-money-signal-system/
├── src/signal_system/
│   ├── weighting_engine/
│   │   ├── __init__.py
│   │   ├── config.py          # WeightingConfig dataclasses
│   │   └── engine.py          # TraderWeightingEngine
│   └── signal_generation/
│       └── processor.py       # ML-enhanced signal generation
```

**Timeline**: 2-3 days

---

### Phase 4: ML Components (smart-money-signal-system)

**Goal**: Feature importance and regime detection

**Files to create**:
```
smart-money-signal-system/
├── src/signal_system/
│   ├── ml/
│   │   ├── feature_importance.py
│   │   ├── regime_detection.py
│   │   └── model_registry.py
│   └── training/
│       ├── train_features.py   # Offline training scripts
│       └── train_regime.py
```

**Timeline**: 3-4 days

---

### Phase 5: Whale Alerts (smart-money-signal-system)

**Goal**: Real-time whale position change detection

**Files to create**:
```
smart-money-signal-system/
├── src/signal_system/
│   └── whale_alerts/
│       ├── detector.py
│       └── alert_store.py
```

**Timeline**: 1-2 days

---

## Integration Testing

### Test Strategy

```python
# tests/test_integration.py

async def test_end_to_end_signal():
    # 1. market-scraper emits trader_positions event
    await redis.publish("trader_positions", test_event)
    
    # 2. smart-money-signal-system processes event
    signal = await signal_system.process(test_event)
    
    # 3. Verify signal is correct
    assert signal.action in ["BUY", "SELL", "NEUTRAL"]
    assert 0 <= signal.confidence <= 1
```

### Test Environment

```bash
# docker-compose for testing (not production)
services:
  redis:
    image: redis:latest
  market-scraper:
    build: ./market-scraper
  smart-money-signal-system:
    build: ./smart-money-signal-system
```

---

## Decision Matrix

| Criteria | Monolithic | Separate | Winner |
|----------|------------|----------|--------|
| Initial Setup | ✅ Simpler | ❌ More complex | Monolithic |
| Long-term Maintenance | ❌ Coupled | ✅ Independent | Separate |
| ML Iteration Speed | ❌ Slow | ✅ Fast | Separate |
| Deployment Flexibility | ❌ All or nothing | ✅ Independent | Separate |
| Team Organization | ❌ Everyone knows everything | ✅ Specialized roles | Separate |
| Testing | ❌ Complex test matrix | ✅ Isolated tests | Separate |
| 2026 Best Practice | ❌ Outdated | ✅ Industry standard | Separate |

**Overall Winner**: **Separate Repositories**

---

## Final Recommendation

### Do This:

1. **Keep market-scraper as data infrastructure only**
   - Data collection
   - Event publishing
   - Basic storage

2. **Build smart-money-signal-system as intelligence layer**
   - ML components
   - Weighting engine
   - Signal generation
   - Whale alerts
   - API for clients

3. **Connect via Redis Event Bus**
   - market-scraper publishes events
   - smart-money-signal-system subscribes and processes

4. **Separate training from inference**
   - Training scripts run offline (weekly/monthly)
   - Inference runs in production (real-time)

### Don't Do This:

- ❌ Add scikit-learn to market-scraper dependencies
- ❌ Mix ML training code with data collection
- ❌ Deploy ML models in market-scraper process
- ❌ Block real-time signals on ML training

---

## Timeline Impact

| Phase | Original (Monolithic) | Revised (Separate) | Change |
|-------|----------------------|-------------------|--------|
| Phase 1: Foundation | 1-2 days | 1-2 days | No change |
| Phase 2: Setup | N/A | 2-3 days | +2-3 days |
| Phase 3: Weighting | 2-3 days | 2-3 days | No change |
| Phase 4: ML | 3-4 days | 3-4 days | No change |
| Phase 5: Alerts | 1-2 days | 1-2 days | No change |

**Total**: +2-3 days for initial setup, but **much better long-term maintainability**

---

## Conclusion

**Yes, ML features should be in smart-money-signal-system, NOT in market-scraper.**

This aligns with:
- ✅ 2026 industry best practices (Nansen, Glassnode)
- ✅ Clean architecture principles (separation of concerns)
- ✅ Your environment constraints (Ubuntu bare metal, no Docker)
- ✅ Long-term maintainability (independent deployment cycles)

**Next Step**: Create smart-money-signal-system repository structure with Redis event bus integration.

---

*Architecture recommendation by Chief Architect & Lead Researcher*
*Powered by 2026 industry research and best practices*
