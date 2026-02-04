#!/bin/bash
# Hyperliquid Largest User Deposits API
# Endpoint: https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors
# Description: Returns top 1,000 users by deposit amount

OUTPUT_FILE="largest_user_depositors.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors"

echo "📥 Downloading Largest User Deposits..."
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
