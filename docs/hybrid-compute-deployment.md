# cryptoOS Deployment Status

**Date:** 2026-07-01
**Status:** VPS-only deployment

## Current Architecture

cryptoOS is deployed as a single Python service on a VPS:

- `market-scraper.service` on port `3845` (managed via systemd)
- Caddy reverse-proxies public traffic to the local service
- Redis and MongoDB are external service dependencies

## What is in the repo

- `market-scraper/` — market data collection and API service (active)
- `smart-money-signal-system/` — signal generation research module (code only, not deployed)
- `shared/` — shared Pydantic/config utilities
- `systemd/` — systemd unit files for market-scraper
- `scripts/` — helper scripts for local startup/status/stop

## Verification

```bash
curl http://localhost:3845/health/live
```

## Notes

- The `smart-money-signal-system/` package is **not deployed**. Its systemd unit has been removed.
- This repository does **not** use Docker for deployment.
- Production workflow is systemd-based, with local scripts for development convenience.