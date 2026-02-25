#!/bin/bash
# Stop all CryptoData platform servers
# Usage: ./scripts/stop-all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

echo "=========================================="
echo "  CryptoData Platform - Stopping Servers"
echo "=========================================="
echo ""

# Function to stop a server
stop_server() {
    local name="$1"
    local pid_file="$LOG_DIR/${name}.pid"

    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $name (PID: $pid)..."
            kill "$pid"
            
            # Wait for graceful shutdown (max 10 seconds)
            for i in {1..10}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    echo "  ✓ $name stopped gracefully"
                    rm -f "$pid_file"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill if still running
            echo "  ⚠ $name didn't stop gracefully, force killing..."
            kill -9 "$pid" 2>/dev/null || true
            rm -f "$pid_file"
            echo "  ✓ $name force stopped"
        else
            echo "  ⚠ $name not running (stale PID file)"
            rm -f "$pid_file"
        fi
    else
        # Try to find by process name
        local pid=$(pgrep -f "$name.*server" 2>/dev/null | head -1)
        if [[ -n "$pid" ]]; then
            echo "Stopping $name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            echo "  ✓ $name stopped"
        else
            echo "  - $name not running"
        fi
    fi
}

stop_server "market-scraper"
stop_server "signal-system"

echo ""
echo "=========================================="
echo "  All servers stopped"
echo "=========================================="
