#!/bin/bash
# Download Hyperliquid Cross Margin Summary

set -e

API_URL="https://api.hyperliquid.xyz/info"
USER_ADDRESS="${1:-0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2}"
OUTPUT_FILE="${2:-data/hyperliquid/cross_margin_summary.json}"

echo "📊 Downloading crossMarginSummary for $USER_ADDRESS..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"crossMarginSummary\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
