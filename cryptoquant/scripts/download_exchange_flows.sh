#!/bin/bash
# Download Exchange Flow Data

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/exchange_flows"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Exchange Flows..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { exchangeFlows { exchangeReserve { value change24h change7d timestamp } exchangeNetflow { value change24h } exchangeInflow { value change24h } exchangeOutflow { value change24h } whaleRatio { value change24h } } } }"}' \
    -o "$OUTPUT_DIR/all_exchange_flows.json"

echo "✅ Saved to $OUTPUT_DIR/all_exchange_flows.json"
ls -lh "$OUTPUT_DIR"
