#!/bin/bash
# Download Exchange Reserve specifically

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/exchange_flows"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Exchange Reserve..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { exchangeFlows { exchangeReserve { value change24h change7d timestamp history(limit:365) { timestamp value } } } } }"}' \
    -o "$OUTPUT_DIR/exchange_reserve.json"

echo "✅ Saved to $OUTPUT_DIR/exchange_reserve.json"
ls -lh "$OUTPUT_DIR/exchange_reserve.json"
