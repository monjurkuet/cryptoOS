#!/bin/bash
# Download Hyperliquid Spot Orderbook

set -e

API_URL="https://api.hyperliquid.xyz/info"
SYMBOL="${1:-HYPE}"
OUTPUT_FILE="${2:-data/hyperliquid/spot_orderbook_${SYMBOL}.json}"

echo "📚 Downloading spotOrderbook for $SYMBOL..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"spotOrderbook\",\"symbol\":\"$SYMBOL\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
