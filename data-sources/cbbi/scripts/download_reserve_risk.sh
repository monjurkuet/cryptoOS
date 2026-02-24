#!/bin/bash
# Download Coinank Reserve Risk Data

API_URL="https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/reserve-risk/"
OUTPUT_FILE="data/coinank/reserve_risk.json"

echo "📥 Downloading Reserve Risk data..."
curl -s -X GET "$API_URL" \
  -H "Content-Type: application/json" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
