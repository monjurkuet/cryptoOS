#!/bin/bash
# Download Hyperliquid Daily Notional Liquidated by Coin

set -e

OUTPUT_FILE="data/daily_notional_liquidated_by_coin.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/daily_notional_liquidated_by_coin"

echo "💸 Downloading Daily Notional Liquidated..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
