#!/bin/bash
# Download Hyperliquid Cumulative USD Volume

set -e

OUTPUT_FILE="data/cumulative_usd_volume.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/cumulative_usd_volume"

echo "📊 Downloading Cumulative USD Volume..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
