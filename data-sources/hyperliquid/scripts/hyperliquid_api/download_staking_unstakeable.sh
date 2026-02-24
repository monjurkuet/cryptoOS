#!/bin/bash
# Download Hyperliquid Staking Unstakeable

set -e

API_URL="https://api.hyperliquid.xyz/info"
USER_ADDRESS="${1:-0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2}"
OUTPUT_FILE="${2:-data/hyperliquid/staking_unstakeable.json}"

echo "🥩 Downloading stakingUnstakeable for $USER_ADDRESS..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"stakingUnstakeable\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
