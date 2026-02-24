#!/bin/bash
# Hyperliquid Largest Users by USD Volume API
# Endpoint: https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume
# Description: Returns top 1,000 users by trading volume

OUTPUT_FILE="largest_users_by_usd_volume.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume"

echo "📥 Downloading Largest Users by USD Volume..."
curl -sL "$URL" -o "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Saved: $OUTPUT_FILE ($SIZE)"
    
    # Count records
    RECORD_COUNT=$(grep -o '"name"' "$OUTPUT_FILE" | wc -l)
    echo "📊 Total Records: $RECORD_COUNT"
    
    # Show sample
    echo ""
    echo "Sample records:"
    head -20 "$OUTPUT_FILE"
    echo ""
else
    echo "❌ Failed to download"
fi
