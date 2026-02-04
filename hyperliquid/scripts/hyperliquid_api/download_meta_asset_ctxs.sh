#!/bin/bash
# Download Hyperliquid Meta and Asset Context

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/meta_asset_ctxs.json}"

echo "🌐 Downloading metaAndAssetCtxs..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"metaAndAssetCtxs"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
