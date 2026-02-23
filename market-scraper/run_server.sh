#!/bin/bash
# Market Scraper Server Control Script
# Usage: ./run_server.sh [start|stop|status|restart] [OPTIONS]
#
# Options:
#   -f, --foreground    Run in foreground (output to terminal)
#   -l, --log-level     Set log level (DEBUG, INFO, WARNING, ERROR)
#   -h, --help          Show this help

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"
DEFAULT_LOG_LEVEL="INFO"
SERVER_PORT="${SERVER_PORT:-8000}"

# Kill any process using the server port
kill_port_process() {
    local port="$1"
    local pid=$(lsof -t -i:"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Killing process $pid on port $port..."
        kill "$pid" 2>/dev/null
        sleep 1
        # Force kill if still running
        if lsof -t -i:"$port" &>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
    fi
}

show_help() {
    echo "Market Scraper Server Control Script"
    echo ""
    echo "Usage: $0 {start|stop|status|restart|run} [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start     Start the server in background"
    echo "  stop      Stop the server"
    echo "  status    Check if server is running"
    echo "  restart   Restart the server"
    echo "  run       Run server in foreground (for development)"
    echo ""
    echo "Options:"
    echo "  -f, --foreground    Run in foreground (output to terminal)"
    echo "  -l, --log-level L   Set log level (DEBUG, INFO, WARNING, ERROR)"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 start                      # Start in background with INFO log level"
    echo "  $0 start -l DEBUG             # Start in background with DEBUG log level"
    echo "  $0 run                        # Run in foreground (terminal output)"
    echo "  $0 start -f                   # Start in foreground mode"
    echo "  $0 stop                       # Stop the server"
    echo "  $0 status                     # Check server status"
    echo "  $0 restart                    # Restart the server"
    echo ""
    echo "Environment:"
    echo "  SERVER_PORT=8000              # Port to use (default: 8000)"
}

start_server() {
    local log_level="${1:-$DEFAULT_LOG_LEVEL}"
    local foreground="${2:-false}"

    # Kill any existing process on the port
    kill_port_process "$SERVER_PORT"

    if [ "$foreground" = "true" ]; then
        echo "Starting server in foreground (CTRL+C to stop)..."
        cd "$SCRIPT_DIR"
        LOG_LEVEL=$log_level uv run python -m market_scraper server
        return
    fi

    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Server already running with PID $(cat $PID_FILE)"
        return 1
    fi

    cd "$SCRIPT_DIR"
    LOG_LEVEL=$log_level uv run python -m market_scraper server >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Server started with PID $(cat $PID_FILE)"
    echo "Log file: $LOG_FILE"
    echo ""
    echo "Commands:"
    echo "  tail -f $LOG_FILE  # Follow logs"
    echo "  $0 status          # Check status"
    echo "  $0 stop            # Stop server"
}

stop_server() {
    # Try PID file first
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo "Server stopped (PID: $PID)"
            return
        else
            echo "Server process not running (stale PID file removed)"
            rm -f "$PID_FILE"
        fi
    fi

    # Fallback: kill by port
    local port_pid=$(lsof -t -i:"$SERVER_PORT" 2>/dev/null)
    if [ -n "$port_pid" ]; then
        echo "Killing process $port_pid on port $SERVER_PORT..."
        kill "$port_pid" 2>/dev/null
        echo "Server stopped"
        return
    fi

    # Last resort: kill by process name
    if pkill -f "market_scraper" 2>/dev/null; then
        echo "Killed any remaining market_scraper processes"
    else
        echo "No server process found"
    fi
}

status_server() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "Server running with PID $(cat $PID_FILE)"
        return 0
    else
        echo "Server not running"
        return 1
    fi
}

# Parse arguments
COMMAND=""
LOG_LEVEL="$DEFAULT_LOG_LEVEL"
FOREGROUND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--foreground)
            FOREGROUND=true
            shift
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        start|stop|status|restart|run)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Handle 'run' as alias for 'start -f'
if [ "$COMMAND" = "run" ]; then
    COMMAND="start"
    FOREGROUND=true
fi

case "$COMMAND" in
    start)  start_server "$LOG_LEVEL" "$FOREGROUND" ;;
    stop)   stop_server ;;
    status) status_server ;;
    restart) stop_server; sleep 1; start_server "$LOG_LEVEL" "$FOREGROUND" ;;
    "")
        show_help
        exit 1
        ;;
esac
