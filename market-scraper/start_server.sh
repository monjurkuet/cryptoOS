#!/bin/bash
pkill -f "market_scraper" 2>/dev/null || true
sleep 1
cd /home/muham/development/cryptodata/market-scraper
LOG_LEVEL=INFO uv run python -m market_scraper server > server.log 2>&1 &
echo "Server started, PID: $!"
