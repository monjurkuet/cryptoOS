# cryptoOS Docs Index

This directory contains cross-project documentation for `cryptoOS`.

## Current Operational Docs

- `hybrid-compute-deployment.md`: deployment guidance for hybrid compute environments.
- `trader-position-api.md`: trader position API contracts and usage.
- `binance-account-positions.md`: saved Binance account position setup and API.

## Planning and Reports

Historical one-off plans/reports were pruned during the zero-debt pass.
Runtime behavior and architecture are now documented only in current subsystem docs.

- `reports/2026-05-12-binance-positions-audit.md`: implementation audit for saved Binance account positions.

## Archival Policy

1. Keep runtime truth in subsystem docs:
   - `market-scraper/README.md`
   - `smart-money-signal-system/README.md`
   - `smart-money-signal-system/docs/architecture.md`
2. Prefer concise architecture and operations docs over long-lived implementation diaries.
3. Remove stale planning documents once their content is superseded and operationally irrelevant.
