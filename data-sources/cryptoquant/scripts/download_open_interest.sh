#!/bin/bash
# Download Open Interest specifically

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/derivatives"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Open Interest..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { derivatives { openInterest { value change24h unit timestamp history(limit:100) { timestamp value } } } } }"}' \
    -o "$OUTPUT_DIR/open_interest.json"

echo "✅ Saved to $OUTPUT_DIR/open_interest.json"
ls -lh "$OUTPUT_DIR/open_interest.json"
