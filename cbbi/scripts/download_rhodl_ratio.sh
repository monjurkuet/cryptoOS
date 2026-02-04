#!/bin/bash
# Download Coinank RHODL Ratio Data

API_URL="https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/rhodl-ratio/"
OUTPUT_FILE="data/coinank/rhodl_ratio.json"

echo "📥 Downloading RHODL Ratio data..."
curl -s -X GET "$API_URL" \
  -H "Content-Type: application/json" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
