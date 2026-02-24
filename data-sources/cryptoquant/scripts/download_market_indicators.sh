#!/bin/bash
# Download Market Indicator Data

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/market_indicators"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Market Indicators..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { marketIndicator { mvrvRatio { value change24h change7d timestamp } estimatedLeverageRatio { value change24h } spotAverageOrderSize { value change24h } futuresAverageOrderSize { value change24h } spotTakerCVD { value status } futuresTakerCVD { value status } spotVolumeBubbleMap { status } futuresVolumeBubbleMap { status } spotRetailActivity { status } futuresRetailActivity { status } } } }"}' \
    -o "$OUTPUT_DIR/all_market_indicators.json"

echo "✅ Saved to $OUTPUT_DIR/all_market_indicators.json"
ls -lh "$OUTPUT_DIR"
