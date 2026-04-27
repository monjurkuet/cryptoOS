#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

echo "Bootstrapping cryptoOS services..."

mkdir -p "$LOG_DIR"
for log_file in \
  "$LOG_DIR/market-scraper.log" \
  "$LOG_DIR/market-scraper.error.log" \
  "$LOG_DIR/signal-system.log" \
  "$LOG_DIR/signal-system.error.log"; do
  if ! touch "$log_file" 2>/dev/null; then
    echo "Warning: unable to write $log_file (continuing)"
  fi
done

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Virtualenv missing, running uv sync..."
  cd "$PROJECT_DIR"
  /home/administrator/.local/bin/uv sync --frozen
fi

echo "Checking Redis..."
redis-cli ping >/dev/null

echo "Checking Mongo connectivity..."
"$VENV_PYTHON" - <<'PY'
from pymongo import MongoClient
from market_scraper.core.config import get_settings
from signal_system.config import get_settings as get_signal_settings

market_settings = get_settings()
signal_settings = get_signal_settings()

client = MongoClient(market_settings.mongo.url, serverSelectionTimeoutMS=5000)
client.admin.command("ping")
client.close()

signal_client = MongoClient(signal_settings.mongo.url, serverSelectionTimeoutMS=5000)
signal_client.admin.command("ping")
signal_client.close()
PY

echo "Bootstrap checks passed."
