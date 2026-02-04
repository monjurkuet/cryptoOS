#!/bin/bash
# Download Hyperliquid Funding Rate

set -e

OUTPUT_FILE="data/funding_rate.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/funding_rate"

echo "📈 Downloading Funding Rate (large file ~12 MB)..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
