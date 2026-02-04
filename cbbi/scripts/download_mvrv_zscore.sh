#!/bin/bash
# Download Coinank MVRV Z-Score Data

API_URL="https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/mvrv-zscore/"
OUTPUT_FILE="data/coinank/mvrv_zscore.json"

echo "📥 Downloading MVRV Z-Score data..."
curl -s -X GET "$API_URL" \
  -H "Content-Type: application/json" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
