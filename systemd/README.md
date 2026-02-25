# systemd Service Files

Production systemd service definitions for CryptoData platform.

## Overview

This directory contains systemd service files for running the CryptoData platform in production:

- **market-scraper.service**: Real-time market data collection and API (port 8000)
- **signal-system.service**: Smart money signal generation (port 4341)

### Features

- ✅ Automatic restart on failure
- ✅ Boot-time startup
- ✅ Centralized logging via `journalctl`
- ✅ Resource limits (memory, CPU)
- ✅ Graceful shutdown handling
- ✅ Security hardening

## Installation

### 1. Copy service files

```bash
sudo cp /home/muham/development/cryptodata/systemd/market-scraper.service /etc/systemd/system/
sudo cp /home/muham/development/cryptodata/systemd/signal-system.service /etc/systemd/system/
```

### 2. Reload systemd daemon

```bash
sudo systemctl daemon-reload
```

### 3. Enable services (start on boot)

```bash
sudo systemctl enable market-scraper.service
sudo systemctl enable signal-system.service
```

### 4. Start services

```bash
sudo systemctl start market-scraper.service
sudo systemctl start signal-system.service
```

### 5. Verify installation

```bash
# Check status
sudo systemctl status market-scraper.service
sudo systemctl status signal-system.service

# Test API endpoints
curl http://localhost:8000/health
curl http://localhost:4341/health
```

## Management Commands

### Check status
```bash
sudo systemctl status market-scraper.service
sudo systemctl status signal-system.service
```

### View logs
```bash
# Using journalctl
sudo journalctl -u market-scraper.service -f
sudo journalctl -u signal-system.service -f

# Or view log files directly
tail -f /home/muham/development/cryptodata/logs/market-scraper.log
tail -f /home/muham/development/cryptodata/logs/signal-system.log
```

### Restart services
```bash
sudo systemctl restart market-scraper.service
sudo systemctl restart signal-system.service
```

### Stop services
```bash
sudo systemctl stop market-scraper.service
sudo systemctl stop signal-system.service
```

### Disable services (don't start on boot)
```bash
sudo systemctl disable market-scraper.service
sudo systemctl disable signal-system.service
```

## Service Dependencies

```
signal-system.service
    └── Requires: market-scraper.service
    └── Wants: redis.service
    └── After: network.target, redis.service, market-scraper.service

market-scraper.service
    └── Wants: mongodb.service, redis.service
    └── After: network.target, mongodb.service, redis.service
```

## Alternative: Bash Scripts

For development or non-systemd environments, use the provided bash scripts:

```bash
# Start both servers in background
./scripts/start-all.sh --background

# Check status
./scripts/status.sh

# View logs
tail -f logs/market-scraper.log
tail -f logs/signal-system.log

# Stop all servers
./scripts/stop-all.sh
```

Bash scripts are suitable for:
- Development environments
- Testing deployments
- Systems without systemd
- Quick manual starts

systemd services are recommended for:
- Production servers
- Automatic restart on crash
- Boot-time startup
- Centralized logging
- Resource management

## Resource Limits

| Service | Memory Max | CPU Quota |
|---------|-----------|-----------|
| market-scraper | 1GB | 80% |
| signal-system | 512MB | 40% |

## Troubleshooting

### Service won't start
```bash
# Check for errors
sudo journalctl -u market-scraper.service -n 50 --no-pager

# Test configuration
sudo systemd-analyze verify /etc/systemd/system/market-scraper.service
```

### Service crashes repeatedly
```bash
# Check restart count
systemctl show market-scraper.service | grep Restart

# View recent crashes
sudo journalctl -u market-scraper.service -p err -n 20
```

### Permission issues
```bash
# Ensure user has access
ls -la /home/muham/development/cryptodata/

# Check uv path
which uv
```
