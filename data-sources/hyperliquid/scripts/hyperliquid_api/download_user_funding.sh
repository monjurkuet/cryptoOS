#!/bin/bash
# Download Hyperliquid User Funding History

set -e

API_URL="https://api.hyperliquid.xyz/info"
USER_ADDRESS="${1:-0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2}"
START_TIME="${2:-1704067200000}"
OUTPUT_FILE="${3:-data/hyperliquid/user_funding.json}"

echo "💸 Downloading userFunding for $USER_ADDRESS..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userFunding\",\"user\":\"$USER_ADDRESS\",\"startTime\":$START_TIME}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
