#!/bin/bash
# Download Hyperliquid Recent Transactions

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/recent_transactions.json}"

echo "📊 Downloading recentTransactions..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"recentTransactions"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
