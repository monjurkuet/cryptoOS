#!/bin/bash
# Download Hyperliquid Daily Unique Users

set -e

OUTPUT_FILE="data/daily_unique_users.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/daily_unique_users"

echo "👤 Downloading Daily Unique Users..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
