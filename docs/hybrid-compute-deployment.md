# cryptoOS Deployment Status

**Date:** 2026-05-06
**Status:** VPS-only deployment

## Current Architecture

cryptoOS is deployed as a pair of Python services on a VPS:

- `market-scraper.service` on port `3845`
- `signal-system.service` on port `4341`
- Caddy routes public traffic to the appropriate local service
- Redis and MongoDB are external service dependencies

## What is in the repo

- `market-scraper/` — market data collection and API service
- `smart-money-signal-system/` — signal generation and RL tuning service
- `shared/` — shared Pydantic/config utilities
- `systemd/` — systemd unit files and deployment notes
- `scripts/` — helper scripts for local startup/status/stop flows

## Verification

```bash
curl http://localhost:3845/health/live
curl http://localhost:4341/health
```

## Notes

- This repository does **not** use Docker for deployment.
- Any stale Docker references from prior experiments should be treated as historical only.
- Production workflow is systemd-based, with local scripts kept only for convenience during development.
