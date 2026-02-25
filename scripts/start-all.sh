#!/bin/bash
# Start all CryptoData platform servers
# Usage: ./scripts/start-all.sh [--background]
#
# Options:
#   --background, -b    Run servers in background (detached mode)

set -e

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

echo "=========================================="
echo "  CryptoData Platform - Starting Servers"
echo "=========================================="
echo ""

# Function to start a server
start_server() {
    local name="$1"
    local dir="$2"
    local module="$3"
    local log_file="$LOG_DIR/${name}.log"
    local pid_file="$LOG_DIR/${name}.pid"

    echo "Starting $name..."
    cd "$dir"

    if $BACKGROUND; then
        # Run in background
        uv run python -m "$module" server >> "$log_file" 2>&1 &
        local pid=$!
        echo $pid > "$pid_file"
        echo "  ✓ $name started (PID: $pid, Log: $log_file)"
    else
        # Run in foreground (will block)
        echo "  → $name (foreground, Ctrl+C to stop)"
        uv run python -m "$module" server
    fi
}

if $BACKGROUND; then
    # Start both servers in background
    start_server "market-scraper" "$PROJECT_DIR/market-scraper" "market_scraper"
    start_server "signal-system" "$PROJECT_DIR/smart-money-signal-system" "signal_system"
    
    echo ""
    echo "=========================================="
    echo "  All servers started successfully!"
    echo "=========================================="
    echo ""
    echo "Services:"
    echo "  - market-scraper:  http://localhost:8000"
    echo "  - signal-system:   http://localhost:4341"
    echo ""
    echo "Logs:"
    echo "  - market-scraper:  $LOG_DIR/market-scraper.log"
    echo "  - signal-system:   $LOG_DIR/signal-system.log"
    echo ""
    echo "To stop all servers:"
    echo "  ./scripts/stop-all.sh"
    echo ""
    echo "To view logs:"
    echo "  tail -f $LOG_DIR/market-scraper.log"
    echo "  tail -f $LOG_DIR/signal-system.log"
else
    # Run in foreground - both servers need to run concurrently
    echo "Starting servers in foreground (press Ctrl+C to stop all)..."
    echo ""
    
    # Start market-scraper in background
    start_server "market-scraper" "$PROJECT_DIR/market-scraper" "market_scraper" &
    MARKET_PID=$!
    
    # Start signal-system in foreground
    start_server "signal-system" "$PROJECT_DIR/smart-money-signal-system" "signal_system"
    
    # Wait for market-scraper to finish (shouldn't happen unless crashed)
    wait $MARKET_PID
fi
