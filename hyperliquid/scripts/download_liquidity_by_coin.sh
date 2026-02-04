#!/bin/bash
# Download Hyperliquid Liquidity by Coin

set -e

OUTPUT_FILE="data/liquidity_by_coin.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/liquidity_by_coin"

echo "💧 Downloading Liquidity by Coin (largest file ~47 MB)..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
