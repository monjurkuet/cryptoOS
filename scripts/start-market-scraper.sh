#!/bin/bash
# Start only the market scraper server
# Usage: ./scripts/start-market-scraper.sh [--background]
#
# Options:
#   --background, -b    Run server in background (detached mode)

set -e

# Unset DEBUG if set to non-boolean value (prevents pydantic-settings crash)
if [[ "${DEBUG:-}" != "true" && "${DEBUG:-}" != "false" && "${DEBUG:-}" != "1" && "${DEBUG:-}" != "0" && -n "${DEBUG:-}" ]]; then
    unset DEBUG
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

# Parse arguments
BACKGROUND=false
if [[ "$1" == "--background" || "$1" == "-b" ]]; then
    BACKGROUND=true
fi

# Create logs directory
mkdir -p "$LOG_DIR"

NAME="market-scraper"
DIR="$PROJECT_DIR/market-scraper"
MODULE="market_scraper"
LOG_FILE="$LOG_DIR/${NAME}.log"
PID_FILE="$LOG_DIR/${NAME}.pid"

echo "=========================================="
echo "  CryptoData - Starting $NAME"
echo "=========================================="
echo ""

cd "$DIR"

if $BACKGROUND; then
    uv run python -m "$MODULE" server >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    echo "  ✓ $NAME started (PID: $PID, Log: $LOG_FILE)"
    echo ""
    echo "Endpoint: http://localhost:3845"
    echo "Health:   http://localhost:3845/health"
    echo ""
    echo "To stop:  kill $PID"
    echo "To view:  tail -f $LOG_FILE"
else
    echo "  → $NAME (foreground, Ctrl+C to stop)"
    uv run python -m "$MODULE" server
fi
