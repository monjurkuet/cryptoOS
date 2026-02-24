#!/bin/bash
# Download Hyperliquid Spot Meta

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/spot_meta.json}"

echo "🪙 Downloading spotMeta..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"spotMeta"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
