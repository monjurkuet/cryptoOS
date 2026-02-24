#!/bin/bash
# Download Hyperliquid Funding History for a coin

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
OUTPUT_FILE="${2:-data/hyperliquid/funding_history_${COIN}.json}"

echo "💸 Downloading fundingHistory for $COIN..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"fundingHistory\",\"coin\":\"$COIN\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
