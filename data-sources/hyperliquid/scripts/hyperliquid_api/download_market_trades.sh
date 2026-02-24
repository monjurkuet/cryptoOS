#!/bin/bash
# Download Hyperliquid Market Trades

set -e

API_URL="https://api.hyperliquid.xyz/info"
COIN="${1:-BTC}"
OUTPUT_FILE="${2:-data/hyperliquid/market_trades_${COIN}.json}"

echo "📈 Downloading marketTrades for $COIN..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"marketTrades\",\"coin\":\"$COIN\"}" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
