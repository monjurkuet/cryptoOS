# Deployment Guide

This guide covers deploying the Market Scraper Framework in production using Docker.

## Docker Deployment

### Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| Services | docker-compose.yml | examples/docker-compose.prod.yml |
| Restart Policy | no | unless-stopped |
| Log Driver | default | json-file with rotation |
| Health Checks | optional | required |
| Resource Limits | none | recommended |

## Quick Production Start

```bash
# Copy production example
cp examples/docker-compose.prod.yml docker-compose.prod.yml

# Start production stack
docker-compose -f docker-compose.prod.yml up -d
```

## Production Docker Compose

The production configuration includes:

- **Market Scraper API**: Main application
- **Redis**: Event bus and caching
- **MongoDB**: Data persistence
- **Nginx** (optional): Reverse proxy and SSL termination

```yaml
version: '3.8'

services:
  market-scraper:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: market-scraper-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - REDIS__URL=redis://redis:6379
      - MONGO__URL=mongodb://mongodb:27017
      - MONGO__DATABASE=market_scraper
      - ENVIRONMENT=production
      - DEBUG=false
    depends_on:
      redis:
        condition: service_healthy
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

  redis:
    image: redis:7-alpine
    container_name: market-scraper-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  mongodb:
    image: mongo:7
    container_name: market-scraper-mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    volumes:
      - mongodb-data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER:-admin}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 3s
      retries: 5

volumes:
  redis-data:
  mongodb-data:
```

## Environment Configuration

### Required Environment Variables

```bash
# Application
APP_NAME=market-scraper
ENVIRONMENT=production
DEBUG=false

# Redis
REDIS__URL=redis://redis:6379

# MongoDB
MONGO__URL=mongodb://mongodb:27017
MONGO__DATABASE=market_scraper
MONGO_USER=admin
MONGO_PASSWORD=your-secure-password

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### Security Considerations

1. **Use strong passwords**: Generate random passwords for MongoDB
2. **Enable SSL/TLS**: Use Nginx with HTTPS
3. **Restrict access**: Use Docker networks
4. **Secrets management**: Consider using Docker secrets or external secrets management

## Production Build

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "market_scraper.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Building the Image

```bash
docker build -t market-scraper:latest .
```

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

```bash
# View logs
docker-compose logs -f market-scraper

# View last 100 lines
docker-compose logs --tail=100 market-scraper
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs market-scraper

# Check if ports are in use
netstat -tulpn | grep 8000
```

### Can't Connect to Services

```bash
# Verify containers are running
docker-compose ps

# Check network connectivity
docker-compose exec market-scraper ping redis
```

### Performance Issues

1. **Check resource usage**:
   ```bash
   docker stats
   ```

2. **Increase memory limits** in docker-compose.yml

3. **Enable query logging** for MongoDB:
   ```bash
   docker-compose exec mongodb mongosh -u admin -p password --eval "db.setLogLevel(1)"
   ```

### Database Issues

1. **MongoDB connection refused**: Check MONGO__URL and authentication
2. **MongoDB slow queries**: Check indexes and query patterns
3. **Redis memory issues**: Increase --maxmemory or adjust eviction policy

## Scaling

### Horizontal Scaling

Run multiple API instances:

```bash
docker-compose up -d --scale market-scraper=3
```

Use a load balancer (like Nginx) to distribute traffic.

### Vertical Scaling

Adjust resource limits in docker-compose.yml:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 4G
```

## Backup and Recovery

### MongoDB Backup

```bash
# Create backup
docker-compose exec mongodb mongodump --out=/backup/dump

# Copy backup
docker cp market-scraper-mongodb:/backup/dump ./backup/
```

### MongoDB Restore

```bash
# Copy backup to container
docker cp ./backup/dump market-scraper-mongodb:/backup/

# Restore
docker-compose exec mongodb mongorestore /backup/dump
```

## SSL/TLS with Nginx

Example Nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://market-scraper:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Maintenance

### Regular Tasks

1. **Log rotation**: Configure in Docker daemon
2. **Database cleanup**: Automatic via MongoDB TTL indexes (see below)
3. **Security updates**: Rebuild images regularly
4. **Backups**: Schedule regular backups

### Data Retention

MongoDB TTL indexes automatically clean up old data based on configurable retention periods. Configure retention in `config/traders_config.yaml`:

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
mongosh cryptodata --eval "
  db.trader_positions.getIndexes().forEach(i => {
    if (i.expireAfterSeconds) print(i.name, ':', i.expireAfterSeconds / 86400, 'days');
  });
"
```

### Updating

```bash
# Pull latest code
git pull

# Rebuild images
docker-compose build

# Restart services
docker-compose up -d
```
