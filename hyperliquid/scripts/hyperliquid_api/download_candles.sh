#!/bin/bash
# Download Hyperliquid Candles for a coin

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
INTERVAL="${2:-1h}"
START_TIME="${3:-1704067200000}"
OUTPUT_FILE="${4:-data/hyperliquid/candles_${COIN}_${INTERVAL}.json}"

echo "🕯️ Downloading candles for $COIN ($INTERVAL)..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"candles\",\"coin\":\"$COIN\",\"interval\":\"$INTERVAL\",\"startTime\":$START_TIME}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
