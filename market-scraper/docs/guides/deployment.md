# Deployment Guide

This guide covers deploying the Market Scraper Framework in production.

## Prerequisites

- Python 3.11+
- MongoDB 7+
- Redis 7+
- uv (Python package manager)

## Deployment Options

| Method | Use Case | Complexity |
|--------|----------|------------|
| **Bash Scripts** | Development, testing | Low |
| **systemd Services** | Production servers | Medium |
| **Manual** | One-off runs, debugging | Low |

## Quick Start

### Option 1: Bash Scripts (Recommended for Development)

From the project root directory:

```bash
# Start both servers in background
./scripts/start-all.sh --background

# Check status
./scripts/status.sh

# View logs
tail -f logs/market-scraper.log

# Stop all servers
./scripts/stop-all.sh
```

### Option 2: systemd Services (Recommended for Production)

```bash
# Install service files
sudo cp systemd/market-scraper.service /etc/systemd/system/
sudo cp systemd/signal-system.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable market-scraper.service signal-system.service
sudo systemctl start market-scraper.service

# Check status
sudo systemctl status market-scraper.service
```

### Option 3: Manual Start

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
API_PORT=8000
```

### Security Considerations

1. **Use strong passwords**: Generate random passwords for MongoDB
2. **Enable SSL/TLS**: Use a reverse proxy with HTTPS
3. **Restrict access**: Use firewall rules to limit access
4. **Secrets management**: Use environment files with restricted permissions

## Production Deployment

### Using systemd (Recommended)

Pre-configured systemd service files are provided in the `systemd/` directory:

```bash
# Copy service files
sudo cp systemd/market-scraper.service /etc/systemd/system/
sudo cp systemd/signal-system.service /etc/systemd/system/

# Review and customize if needed
sudo vim /etc/systemd/system/market-scraper.service

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable market-scraper.service
sudo systemctl enable signal-system.service

# Start services
sudo systemctl start market-scraper.service
sudo systemctl start signal-system.service

# Check status
sudo systemctl status market-scraper.service
sudo systemctl status signal-system.service
```

#### Service Configuration

The default service files include:

- **Auto-restart** on failure (5 second delay)
- **Resource limits**: 1GB memory, 80% CPU for market-scraper
- **Logging**: stdout/stderr to journal and log files
- **Graceful shutdown**: 30 second timeout
- **Security hardening**: Read-only home, restricted privileges

To customize, edit the service files before copying or use systemd overrides:

```bash
sudo systemctl edit market-scraper.service
```

#### Managing Services

```bash
# Restart
sudo systemctl restart market-scraper.service

# Stop
sudo systemctl stop market-scraper.service

# View logs
sudo journalctl -u market-scraper.service -f

# View recent errors
sudo journalctl -u market-scraper.service -p err -n 50
```

See [systemd/README.md](../../systemd/README.md) for complete documentation.

## Monitoring

### Health Checks

The application provides health check endpoints:

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health with dependencies
curl http://localhost:8000/health/detailed
```

### Metrics

Prometheus metrics are available at:

```bash
curl http://localhost:8000/metrics
```

### Logging

Logs are written to stdout/stderr. View with:

```bash
# systemd logs
journalctl -u market-scraper -f

# Or if running directly
./run_server.sh 2>&1 | tee server.log
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl -u market-scraper -n 100

# Check if ports are in use
ss -tulpn | grep 8000
```

### Can't Connect to Services

```bash
# Verify MongoDB is running
systemctl status mongodb

# Verify Redis is running
systemctl status redis

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
        proxy_pass http://127.0.0.1:8000;
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
sudo systemctl restart market-scraper
```
