#!/bin/bash
# Hyperliquid Top Traders API
# Endpoint: https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
# Description: Returns top 30,000+ traders with performance metrics

OUTPUT_FILE="leaderboard.json"
URL="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

echo "📥 Downloading Top Traders Leaderboard..."
curl -sL "$URL" -o "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Saved: $OUTPUT_FILE ($SIZE)"
    
    # Count records
    TRADER_COUNT=$(grep -o '"ethAddress"' "$OUTPUT_FILE" | wc -l)
    echo "📊 Total Traders: $TRADER_COUNT"
    
    # Show sample
    echo ""
    echo "Sample record:"
    head -c 500 "$OUTPUT_FILE"
    echo ""
else
    echo "❌ Failed to download"
fi
