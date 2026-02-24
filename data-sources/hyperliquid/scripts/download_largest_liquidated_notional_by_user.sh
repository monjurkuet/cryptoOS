#!/bin/bash
# Hyperliquid Largest Liquidations API
# Endpoint: https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user
# Description: Returns top 1,000 users by liquidation amount

OUTPUT_FILE="largest_liquidated_notional_by_user.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user"

echo "📥 Downloading Largest Liquidations..."
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
