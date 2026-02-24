#!/bin/bash
# Download Hyperliquid Cumulative New Users

set -e

OUTPUT_FILE="data/cumulative_new_users.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/cumulative_new_users"

echo "👤 Downloading Cumulative New Users..."
curl -sL "$URL" -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
