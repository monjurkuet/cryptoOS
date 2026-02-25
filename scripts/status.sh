#!/bin/bash
# Check status of all CryptoData platform servers
# Usage: ./scripts/status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

echo "=========================================="
echo "  CryptoData Platform - Server Status"
echo "=========================================="
echo ""

# Function to check server status
check_server() {
    local name="$1"
    local port="$2"
    local pid_file="$LOG_DIR/${name}.pid"
    local log_file="$LOG_DIR/${name}.log"

    echo -n "$name: "

    # Check if port is listening
    if ss -tlnp 2>/dev/null | grep -q ":$port " || netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        local pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' | head -1)
        echo "✓ Running on port $port (PID: $pid)"
        
        # Show recent log if available
        if [[ -f "$log_file" ]]; then
            local last_line=$(tail -1 "$log_file" 2>/dev/null | cut -c1-60)
            if [[ -n "$last_line" ]]; then
                echo "    Last log: $last_line..."
            fi
        fi
    elif [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "⚠ Running (PID: $pid) but port $port not listening"
        else
            echo "✗ Not running (stale PID file)"
        fi
    else
        # Try to find by process name
        local pid=$(pgrep -f "$name.*server" 2>/dev/null | head -1)
        if [[ -n "$pid" ]]; then
            echo "✓ Running (PID: $pid)"
        else
            echo "✗ Not running"
        fi
    fi
}

check_server "market-scraper" "8000"
check_server "signal-system" "4341"

echo ""
echo "Endpoints:"
echo "  - market-scraper API:  http://localhost:8000/api/v1"
echo "  - signal-system API:   http://localhost:4341"
echo ""
echo "Health checks:"
echo "  - curl http://localhost:8000/health"
echo "  - curl http://localhost:4341/health"
