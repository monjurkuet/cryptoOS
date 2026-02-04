#!/bin/bash
# Download Hyperliquid Open Interest

set -e

OUTPUT_FILE="data/open_interest.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/open_interest"

echo "📈 Downloading Open Interest (large file ~12 MB)..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
