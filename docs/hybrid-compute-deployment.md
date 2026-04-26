# Hybrid Compute Deployment Report

**Date:** April 13, 2026
**Status:** ✅ Operational (VPS-only)

## Architecture

```
Internet → VPS (Caddy Reverse Proxy)
              ├── blockchain.datasolved.org → localhost:3845 (market-scraper on VPS)
              ├── search.datasolved.org → localhost:8345 (DDGS API)
              ├── llm.datasolved.org → localhost:8317
              ├── api.datasolved.org → localhost:18080
              └── trading.datasolved.org → localhost:3000

VPS (100.92.181.21)
├── Caddy (reverse proxy)
├── market-scraper.service (port 3845)
└── DDGS API (port 8345)
```

## Components Deployed

### VPS Services
- **Caddy** - Reverse proxy with auto-HTTPS
- **DDGS API** - Running on port 8345
- **market-scraper.service** - Running on port 3845

## Routing Notes

- This deployment is configured as **single-server (VPS-only)**.
- `blockchain.datasolved.org` reverse-proxies only to `localhost:3845` (no Desktop/Tailscale upstream).

## Configuration Files

### Docker Files (cryptoOS repo)
- `Dockerfile` - Multi-stage build for market-scraper
- `docker-compose.yml` - Container orchestration
- `.dockerignore` - Build optimization

### Caddy Routes
- `blockchain.datasolved.org` → `localhost:3845`
- `search.datasolved.org` → `localhost:8345`

## Verification Commands

```bash
# Check market-scraper on VPS
curl http://localhost:3845/health/live

# Check via domain
curl https://blockchain.datasolved.org/health/live
curl https://search.datasolved.org/
```

## Git Commits

### cryptoOS Repository
- `b85b514` - fix: add README.md to Docker build context
- `33add13` - feat: add Docker and docker-compose for hybrid compute deployment

### hermesagent Repository
- `fbb2296` - feat: add Docker API version of hybrid compute failover monitor

## Next Steps (Optional)

1. Add persistent volume mounts for data/logs on Desktop
2. Implement MongoDB events optimization plan
3. Add monitoring/alerting for failover events
4. Set up automated container updates on Desktop
