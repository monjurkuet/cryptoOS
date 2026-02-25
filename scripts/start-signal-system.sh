#!/bin/bash
# Start smart-money-signal-system server
# Usage: ./scripts/start-signal-system.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SIGNAL_SYSTEM_DIR="$PROJECT_DIR/smart-money-signal-system"

cd "$SIGNAL_SYSTEM_DIR"

echo "Starting smart-money-signal-system server..."
echo "Working directory: $(pwd)"
echo "Log file: $SIGNAL_SYSTEM_DIR/logs/server.log"

# Create logs directory if it doesn't exist
mkdir -p "$SIGNAL_SYSTEM_DIR/logs"

# Start the server
exec uv run python -m signal_system server
