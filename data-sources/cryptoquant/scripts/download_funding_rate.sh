#!/bin/bash
# Download Funding Rate specifically

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/derivatives"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Funding Rate..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { derivatives { fundingRate { value change24h timestamp history(limit:100) { timestamp value } } } } }"}' \
    -o "$OUTPUT_DIR/funding_rate.json"

echo "✅ Saved to $OUTPUT_DIR/funding_rate.json"
ls -lh "$OUTPUT_DIR/funding_rate.json"
