#!/bin/bash
# Download Hyperliquid Token Config

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/token_config.json}"

echo "🪙 Downloading tokenConfig..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"tokenConfig"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
