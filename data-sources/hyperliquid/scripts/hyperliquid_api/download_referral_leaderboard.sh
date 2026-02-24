#!/bin/bash
# Download Hyperliquid Referral Leaderboard

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/referral_leaderboard.json}"

echo "🌐 Downloading referralLeaderboard..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"referralLeaderboard"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
