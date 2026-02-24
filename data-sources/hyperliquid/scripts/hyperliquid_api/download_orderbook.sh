#!/bin/bash
# Download Hyperliquid Orderbook for a coin

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
OUTPUT_FILE="${2:-data/hyperliquid/orderbook_${COIN}.json}"

echo "📚 Downloading orderbook for $COIN..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"orderbook\",\"coin\":\"$COIN\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
