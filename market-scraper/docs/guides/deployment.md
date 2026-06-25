# Deployment Guide

This guide covers deploying the Market Scraper Framework in production.

## Prerequisites

- Python 3.11+
- MongoDB 7+
- Redis 7+
- uv (Python package manager)

## Deployment Methods

### Manual Start

```bash
cd market-scraper
uv sync
cp .env.example .env
vim .env  # Edit configuration
uv run python -m market_scraper server
```

## Environment Configuration

### Required Environment Variables

```bash
# Application
APP_NAME=market-scraper
ENVIRONMENT=production
DEBUG=false

# Redis
REDIS__URL=redis://localhost:6379

# MongoDB
MONGO__URL=mongodb://localhost:27017
MONGO__DATABASE=market_scraper

# API
API_HOST=0.0.0.0
API_PORT=3845
```

### Security Considerations

1. **Use strong passwords**: Generate random passwords for MongoDB
2. **Enable SSL/TLS**: Use a reverse proxy with HTTPS
3. **Restrict access**: Use firewall rules to limit access
4. **Secrets management**: Use environment files with restricted permissions

## Production Deployment

## Monitoring

### Health Checks

The application provides health check endpoints:

```bash
# Basic health
curl http://localhost:3845/health/live

# Readiness with all checks
curl http://localhost:3845/health/ready

# Detailed component status
curl http://localhost:3845/health/status
```

### Metrics

Prometheus is managed separately at the system level. This application does not start or expose a local Prometheus metrics server.

Configure your system-level Prometheus deployment to scrape the application and any exporter you manage externally.

### Logging

Logs are written to stdout/stderr. View with:

```bash
# Running directly
uv run python -m market_scraper server 2>&1 | tee server.log

# Or redirect to file
uv run python -m market_scraper server > logs/market-scraper.log 2>&1 &
```

## Troubleshooting

### Service Won't Start

```bash
# Check if ports are in use
ss -tulpn | grep 3845

# Check if process is already running
ps aux | grep market_scraper
```

### Can't Connect to Services

```bash
# Test connections
redis-cli ping
mongosh --eval "db.adminCommand('ping')"
```

### Performance Issues

1. **Check resource usage**:
   ```bash
   htop
   ```

2. **Check MongoDB performance**:
   ```bash
   mongosh --eval "db.serverStatus().connections"
   ```

3. **Check Redis memory**:
   ```bash
   redis-cli info memory
   ```

### Database Issues

1. **MongoDB connection refused**: Check MONGO__URL and authentication
2. **MongoDB slow queries**: Check indexes and query patterns
3. **Redis memory issues**: Increase maxmemory or adjust eviction policy

## Backup and Recovery

### MongoDB Backup

```bash
# Create backup
mongodump --db=market_scraper --out=/backup/$(date +%Y%m%d)

# Restore
mongorestore /backup/20240101/market_scraper
```

### Redis Backup

```bash
# Trigger RDB save
redis-cli BGSAVE

# Copy dump file
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

## SSL/TLS with Nginx

Use Nginx as a reverse proxy for SSL termination:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://127.0.0.1:3845;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Maintenance

### Regular Tasks

1. **Log rotation**: Configure logrotate for server.log
2. **Database cleanup**: Automatic via MongoDB TTL indexes
3. **Security updates**: Run `uv sync` regularly
4. **Backups**: Schedule regular backups

### Data Retention

MongoDB TTL indexes automatically clean up old data based on configurable retention periods. Configure retention in `config/market_config.yaml`:

```yaml
storage:
  retention:
    leaderboard_history: 90    # Leaderboard snapshots (days)
    trader_positions: 30       # Position snapshots
    trader_scores: 90          # Score history
    signals: 30                # Trading signals
    trader_signals: 30         # Per-trader signals
    mark_prices: 30            # Mark price data
    trades: 7                  # Raw trade data
    orderbook: 7               # Orderbook snapshots
    candles: 30                # OHLCV candles
```

TTL indexes are created automatically on startup. MongoDB's TTL monitor runs every 60 seconds, so data may persist for up to a minute past the expiration time.

To verify TTL indexes are working:

```bash
# Check TTL indexes
mongosh market_scraper --eval "
  db.trader_positions.getIndexes().forEach(i => {
    if (i.expireAfterSeconds) print(i.name, ':', i.expireAfterSeconds / 86400, 'days');
  });
"
```

### Updating

```bash
# Pull latest code
git pull

# Update dependencies
uv sync

# Restart service
sudo systemctl restart market-scraper.service
```
