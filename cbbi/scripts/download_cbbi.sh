#!/bin/bash
# Download CBBI Main Data

API_URL="https://colintalkscrypto.com/cbbi/data/latest.json"
OUTPUT_FILE="data/cbbi/latest.json"

echo "📥 Downloading CBBI main data..."
curl -s -X GET "$API_URL" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
