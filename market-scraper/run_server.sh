#!/bin/bash
# Start Market Scraper server with verbose logging

# Kill any existing instances
pkill -f "market_scraper" 2>/dev/null || true

# Start server in background with DEBUG logging
LOG_LEVEL=DEBUG uv run python -m market_scraper server > server.log 2>&1 &
SERVER_PID=$!

echo "Server started with PID: $SERVER_PID"
echo "Log file: $(pwd)/server.log"
echo ""
echo "Commands to monitor:"
echo "  tail -f server.log       # Follow live output"
echo "  cat server.log           # Read entire file"
echo "  grep error server.log    # Search for errors"
echo "  pkill -f market_scraper  # Stop server"
