# cryptoOS Docs Index

This directory contains cross-project documentation for `cryptoOS`.

## Current Operational Docs

- `hybrid-compute-deployment.md`: deployment guidance for hybrid compute environments.
- `trader-position-api.md`: trader position API contracts and usage.

## Planning Docs

- `plans/2025-05-01-event-loop-block-fix.md`
- `plans/2026-04-26-rl-signal-agent.md`
- `plans/staggered-ws-ramp-up.md`

Planning docs are historical implementation records. They are not the runtime source of truth.

## Reports

- `reports/2026-04-26-recent-changes-report.md`

Reports are snapshots in time and should be read with their timestamp context.

## Archival Policy

1. Keep docs in `docs/plans/` and `docs/reports/` immutable after execution unless correcting factual errors.
2. Add a new report/plan instead of rewriting old ones when architecture changes materially.
3. Keep runtime truth in subsystem docs:
   - `market-scraper/README.md`
   - `smart-money-signal-system/README.md`
   - `smart-money-signal-system/docs/architecture.md`
4. Remove docs only when they are exact duplicates or broken references with no historical value.
