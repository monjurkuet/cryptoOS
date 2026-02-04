#!/bin/bash
# Download Fund Data (Market Cap, Premiums, etc.)

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/fund_data"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Fund Data..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { fundData { coinbasePremium { value change24h change7d } coinbasePremiumGap { value change24h } koreaPremium { value change24h } stablecoinSupplyRatio { value change24h } marketCap { value change24h } realizedCap { value change24h } averageCap { value change24h } deltaCap { value change24h } thermoCap { value change24h } } } }"}' \
    -o "$OUTPUT_DIR/all_fund_data.json"

echo "✅ Saved to $OUTPUT_DIR/all_fund_data.json"
ls -lh "$OUTPUT_DIR"
