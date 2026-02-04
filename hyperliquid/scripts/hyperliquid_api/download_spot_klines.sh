#!/bin/bash
# Download Hyperliquid Spot Klines (Candles)

set -e

API_URL="https://api.hyperliquid.xyz/info"
SYMBOL="${1:-HYPE}"
INTERVAL="${2:-1h}"
START_TIME="${3:-1704067200000}"
OUTPUT_FILE="${4:-data/hyperliquid/spot_klines_${SYMBOL}_${INTERVAL}.json}"

echo "🕯️ Downloading spotKlines for $SYMBOL ($INTERVAL)..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"spotKlines\",\"symbol\":\"$SYMBOL\",\"interval\":\"$INTERVAL\",\"startTime\":$START_TIME}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
