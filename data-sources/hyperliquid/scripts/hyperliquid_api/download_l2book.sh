#!/bin/bash
# Download Hyperliquid L2 Book (Orderbook)

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
OUTPUT_FILE="${2:-data/hyperliquid/l2book_${COIN}.json}"

echo "📚 Downloading l2Book for $COIN..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"l2Book\",\"coin\":\"$COIN\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
