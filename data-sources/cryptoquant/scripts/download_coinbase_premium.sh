#!/bin/bash
# Download Coinbase Premium specifically

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/fund_data"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Coinbase Premium..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { fundData { coinbasePremium { value change24h change7d timestamp history(limit:100) { timestamp value } } } } }"}' \
    -o "$OUTPUT_DIR/coinbase_premium.json"

echo "✅ Saved to $OUTPUT_DIR/coinbase_premium.json"
ls -lh "$OUTPUT_DIR/coinbase_premium.json"
