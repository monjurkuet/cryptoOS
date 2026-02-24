#!/bin/bash
# Download MVRV Ratio specifically

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/market_indicators"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC MVRV Ratio..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { marketIndicator { mvrvRatio { value change24h change7d timestamp history(limit:365) { timestamp value change24h } } } } }"}' \
    -o "$OUTPUT_DIR/mvrv_ratio.json"

echo "✅ Saved to $OUTPUT_DIR/mvrv_ratio.json"
ls -lh "$OUTPUT_DIR/mvrv_ratio.json"
