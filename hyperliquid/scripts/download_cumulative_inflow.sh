#!/bin/bash
# Hyperliquid Cumulative Inflow API
# Endpoint: https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow
# Description: Returns cumulative inflow data over time

OUTPUT_FILE="cumulative_inflow.json"
URL="https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow"

echo "📥 Downloading Cumulative Inflow..."
curl -sL "$URL" -o "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Saved: $OUTPUT_FILE ($SIZE)"
    
    # Show sample
    echo ""
    echo "Sample data:"
    head -50 "$OUTPUT_FILE"
    echo ""
else
    echo "❌ Failed to download"
fi
