#!/bin/bash
# Download Hyperliquid Liquidation Candidates

set -e

API_URL="https://api.hyperliquid.xyz/info"
OUTPUT_FILE="${1:-data/hyperliquid/liquidation_candidates.json}"

echo "⚠️ Downloading liquidationCandidates..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"liquidationCandidates"}' \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
