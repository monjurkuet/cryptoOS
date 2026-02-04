#!/bin/bash
# Download Hyperliquid Cumulative Trades

set -e

OUTPUT_FILE="data/cumulative_trades.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/cumulative_trades"

echo "📊 Downloading Cumulative Trades..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
