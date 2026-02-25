#!/bin/bash
# Start market-scraper server
# Usage: ./scripts/start-market-scraper.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MARKET_SCRAPER_DIR="$PROJECT_DIR/market-scraper"

cd "$MARKET_SCRAPER_DIR"

echo "Starting market-scraper server..."
echo "Working directory: $(pwd)"
echo "Log file: $MARKET_SCRAPER_DIR/logs/server.log"

# Create logs directory if it doesn't exist
mkdir -p "$MARKET_SCRAPER_DIR/logs"

# Start the server
exec uv run python -m market_scraper server
