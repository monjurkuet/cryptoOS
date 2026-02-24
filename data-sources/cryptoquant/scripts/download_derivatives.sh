#!/bin/bash
# Download Derivatives Data

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/derivatives"

mkdir -p "$OUTPUT_DIR"

echo "📥 Downloading BTC Derivatives Data..."

curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { derivatives { fundingRate { value change24h } openInterest { value change24h } longShortRatio { longRatio shortRatio netPosition } takerVolume { buyVolume sellVolume netVolume } topTraderRatio { longRatio shortRatio } } } }"}' \
    -o "$OUTPUT_DIR/all_derivatives.json"

echo "✅ Saved to $OUTPUT_DIR/all_derivatives.json"
ls -lh "$OUTPUT_DIR"
