#!/bin/bash
# Download Hyperliquid Airdrop Metadata

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/airdrop_metadata.json}"

echo "🎁 Downloading airdropMetadata..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"airdropMetadata"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
