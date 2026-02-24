#!/bin/bash
# Download Hyperliquid Daily USD Volume

set -e

OUTPUT_FILE="data/daily_usd_volume.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/daily_usd_volume"

echo "📊 Downloading Daily USD Volume..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
