# Smart Money Signal System Architecture

## Runtime Topology

- `signal_system.runtime.build_runtime` assembles the live graph.
- `signal_system.api.main` hosts FastAPI and wires shared runtime components into API dependencies.
- `signal_system.services.event_processor.EventProcessor` handles incoming market events and orchestrates:
  - whale detection
  - signal generation
  - signal persistence
  - outcome tracking
  - decision trace persistence

## YAML-Driven Signal Configuration

- Source of truth: `config/signal_system.yaml`
- Loader/store: `signal_system.runtime_config.SignalRuntimeConfigStore`
- Live apply path:
  1. validate payload (`SignalRuntimeConfig` pydantic schema)
  2. persist YAML
  3. apply to runtime via `signal_system.runtime.apply_runtime_config`

## Agent-Managed Config Endpoints

- `GET /api/v1/config/signal`
- `GET /api/v1/config/signal/status`
- `GET /api/v1/config/signal/history`
- `POST /api/v1/config/signal/validate`
- `PUT /api/v1/config/signal`
- `POST /api/v1/config/signal/apply`
- `POST /api/v1/config/signal/reload`

Mutation endpoints require `X-Agent-Token` and are enabled only when `SIGNAL_ADMIN_TOKEN` is configured.

## Auditability and Safety

- Config status includes checksum and modification timestamp.
- Config history is append-only in `config/signal_system.yaml.history.yaml` with bounded retention.
- Parameter update events are persisted via `ParamEventStore`.
- Decision traces capture emitted and suppressed signal decisions.

## Current Verification Baseline

- Unit tests pass with:
  - `PYTHONPATH=src pytest -q tests/unit`
- Runtime config tests:
  - `tests/unit/test_runtime_config.py`
