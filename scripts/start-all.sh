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

# Create logs directory
mkdir -p "$LOG_DIR"

# Function to check port and kill existing process
kill_port() {
    local port="$1"
    local name="$2"
    
    if lsof -i:$port > /dev/null 2>&1; then
        echo "  ⚠ Port $port is in use by $name, killing existing process..."
        PID_TO_KILL=$(lsof -t -i:$port)
        if [ -n "$PID_TO_KILL" ]; then
            kill -9 $PID_TO_KILL 2>/dev/null || true
            sleep 1
        fi
    fi
}

# Function to check and kill stale PID
kill_stale_pid() {
    local name="$1"
    local pid_file="$LOG_DIR/${name}.pid"
    
    if [ -f "$pid_file" ]; then
        local old_pid=$(cat "$pid_file")
        if [ -n "$old_pid" ] && ps -p $old_pid > /dev/null 2>&1; then
            echo "  ⚠ Stale PID file found for $name, killing process $old_pid..."
            kill -9 $old_pid 2>/dev/null || true
            sleep 1
        fi
        rm -f "$pid_file"
    fi
}

# Function to verify port is free
verify_port() {
    local port="$1"
    local name="$2"
    
    if lsof -i:$port > /dev/null 2>&1; then
        echo "  ✗ Error: Port $port is still in use by $name"
        exit 1
    fi
}

# Pre-check: Kill any existing processes on our ports
echo "Checking for existing processes..."
kill_port 3845 "market-scraper"
kill_port 4341 "signal-system"
kill_stale_pid "market-scraper"
kill_stale_pid "signal-system"

# Verify ports are free
verify_port 3845 "market-scraper"
verify_port 4341 "signal-system"

# Parse arguments
BACKGROUND=false
if [[ "$1" == "--background" || "$1" == "-b" ]]; then
    BACKGROUND=true
fi

echo "=========================================="
echo "  CryptoData Platform - Starting Servers"
echo "=========================================="
echo ""

# Function to start a server
start_server() {
    local name="$1"
    local dir="$2"
    local module="$3"
    local port="$4"
    local log_file="$LOG_DIR/${name}.log"
    local pid_file="$LOG_DIR/${name}.pid"

    # Truncate log to last 1000 lines
    if [ -f "$log_file" ]; then
        lines=$(wc -l < "$log_file")
        if [ "$lines" -gt 1000 ]; then
            tail -n 1000 "$log_file" > "$log_file.tmp" && mv "$log_file.tmp" "$log_file"
        fi
    fi

    echo "Starting $name on port $port..."
    cd "$dir"

    if $BACKGROUND; then
        uv run python -m "$module" server >> "$log_file" 2>&1 &
        local pid=$!
        echo $pid > "$pid_file"
        echo "  ✓ $name started (PID: $pid, Log: $log_file)"
    else
        echo "  → $name (foreground, Ctrl+C to stop)"
        uv run python -m "$module" server
    fi
}

if $BACKGROUND; then
    start_server "market-scraper" "$PROJECT_DIR/market-scraper" "market_scraper" 3845
    start_server "signal-system" "$PROJECT_DIR/smart-money-signal-system" "signal_system" 4341
    
    echo ""
    echo "=========================================="
    echo "  All servers started successfully!"
    echo "=========================================="
    echo ""
    echo "Services:"
    echo "  - market-scraper:  http://localhost:3845"
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
    echo "Starting servers in foreground (press Ctrl+C to stop all)..."
    echo ""
    
    start_server "market-scraper" "$PROJECT_DIR/market-scraper" "market_scraper" 3845 &
    MARKET_PID=$!
    
    start_server "signal-system" "$PROJECT_DIR/smart-money-signal-system" "signal_system" 4341
    
    wait $MARKET_PID
fi
