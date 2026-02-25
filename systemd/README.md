# systemd Service Files

Production systemd service definitions for CryptoData platform.

## Installation

### 1. Copy service files to systemd directory

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
