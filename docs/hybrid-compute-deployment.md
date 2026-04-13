# Hybrid Compute Deployment Report

**Date:** April 13, 2026
**Status:** ✅ Operational

## Architecture

```
Internet → VPS (Caddy Reverse Proxy)
              ├── blockchain.datasolved.org → Desktop:3845 (market-scraper)
              ├── search.datasolved.org → localhost:8345 (DDGS API)
              ├── llm.datasolved.org → localhost:8317
              ├── api.datasolved.org → localhost:18080
              └── trading.datasolved.org → localhost:3000

VPS (100.92.181.21)          Desktop (100.90.22.11)
├── hybrid-monitor.service   ├── Docker Desktop 4.67.0
├── Caddy (reverse proxy)    ├── market-scraper container
├── DDGS API (port 8345)     ├── hybrid-redis container
└── (failover capable)       └── heartbeat server (port 8080)
```

## Components Deployed

### Desktop Docker Containers
- **market-scraper** - Running on port 3845, healthy
- **hybrid-redis** - Redis for event bus coordination
- **hybrid-network** - Docker network for inter-container communication

### VPS Services
- **hybrid-monitor.service** - Monitors Desktop heartbeat, handles failover
- **Caddy** - Reverse proxy with auto-HTTPS
- **DDGS API** - Running on port 8345

## Automatic Failover

1. **Desktop Online Detection**: 5-10 seconds
2. **Failover Threshold**: 30 seconds
3. **Switch Time**: ~30-40 seconds total

### Failover Flow
```
Desktop OFFLINE → VPS starts market-scraper.service
Desktop ONLINE → VPS stops market-scraper.service, Desktop Docker runs it
```

## Configuration Files

### Docker Files (cryptoOS repo)
- `Dockerfile` - Multi-stage build for market-scraper
- `docker-compose.yml` - Container orchestration
- `.dockerignore` - Build optimization

### Caddy Routes
- `blockchain.datasolved.org` → `100.90.22.11:3845`
- `search.datasolved.org` → `localhost:8345`

## SSH Access
```bash
ssh muham@100.90.22.11  # Desktop via Tailscale
```

## Docker API Access
```bash
export DOCKER_HOST="tcp://100.90.22.11:2375"
docker ps  # List containers on Desktop
```

## Verification Commands

```bash
# Check Desktop heartbeat
curl http://100.90.22.11:8080/

# Check hybrid monitor status
sudo journalctl -u hybrid-monitor.service -f

# Check market-scraper on Desktop
curl http://100.90.22.11:3845/health/live

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
