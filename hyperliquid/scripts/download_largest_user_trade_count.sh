#!/bin/bash
# Hyperliquid Largest Trade Count API
# Endpoint: https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count
# Description: Returns top 1,000 users by number of trades

OUTPUT_FILE="largest_user_trade_count.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count"

echo "📥 Downloading Largest Trade Count..."
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
