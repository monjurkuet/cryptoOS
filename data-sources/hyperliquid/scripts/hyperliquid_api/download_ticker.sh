#!/bin/bash
# Download Hyperliquid Ticker for a coin

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
OUTPUT_FILE="${2:-data/hyperliquid/ticker_${COIN}.json}"

echo "📈 Downloading ticker for $COIN..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"ticker\",\"coin\":\"$COIN\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
