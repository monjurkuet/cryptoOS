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

NAME="market-scraper"
DIR="$PROJECT_DIR/market-scraper"
MODULE="market_scraper"
PORT=3845
LOG_FILE="$LOG_DIR/${NAME}.log"
PID_FILE="$LOG_DIR/${NAME}.pid"

# Create logs directory
mkdir -p "$LOG_DIR"

# Truncate log to last 1000 lines to prevent unbounded growth
if [ -f "$LOG_FILE" ]; then
    lines=$(wc -l < "$LOG_FILE")
    if [ "$lines" -gt 1000 ]; then
        tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi

# Check if port is in use and kill existing process
if lsof -i:$PORT > /dev/null 2>&1; then
    echo "  ⚠ Port $PORT is in use, killing existing process..."
    PID_TO_KILL=$(lsof -t -i:$PORT)
    if [ -n "$PID_TO_KILL" ]; then
        kill -9 $PID_TO_KILL 2>/dev/null || true
        sleep 1
    fi
fi

# Check for stale PID file and kill if process still exists
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if [ -n "$OLD_PID" ] && ps -p $OLD_PID > /dev/null 2>&1; then
        echo "  ⚠ Stale PID file found, killing process $OLD_PID..."
        kill -9 $OLD_PID 2>/dev/null || true
        sleep 1
    fi
    rm -f "$PID_FILE"
fi

# Verify port is now free
if lsof -i:$PORT > /dev/null 2>&1; then
    echo "  ✗ Error: Port $PORT is still in use"
    exit 1
fi

echo "=========================================="
echo "  CryptoData - Starting $NAME"
echo "=========================================="
echo ""

cd "$DIR"

# Parse arguments
BACKGROUND=false
if [[ "$1" == "--background" || "$1" == "-b" ]]; then
    BACKGROUND=true
fi

if $BACKGROUND; then
    uv run python -m "$MODULE" server >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    echo "  ✓ $NAME started (PID: $PID, Log: $LOG_FILE)"
    echo ""
    echo "Endpoint: http://localhost:$PORT"
    echo "Health:   http://localhost:$PORT/health"
    echo ""
    echo "To stop:  kill $PID"
    echo "To view:  tail -f $LOG_FILE"
else
    echo "  → $NAME (foreground, Ctrl+C to stop)"
    uv run python -m "$MODULE" server
fi
