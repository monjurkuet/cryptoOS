#!/bin/bash
# Download Hyperliquid Vaults

OUTPUT_FILE="vaults.json"
URL="https://stats-data.hyperliquid.xyz/Mainnet/vaults"

echo "📥 Downloading Vaults..."
curl -sL "$URL" -o "$OUTPUT_FILE"

if [ -f "$OUTPUT_FILE" ]; then
    SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Saved: $OUTPUT_FILE ($SIZE)"
    
    # Count vaults
    VAULT_COUNT=$(jq 'length' "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
    echo "📊 Total Vaults: $VAULT_COUNT"
    
    # Show sample
    echo ""
    echo "Sample vault:"
    jq '.[0].summary' "$OUTPUT_FILE" 2>/dev/null || head -c 500 "$OUTPUT_FILE"
    echo ""
else
    echo "❌ Failed to download"
fi
