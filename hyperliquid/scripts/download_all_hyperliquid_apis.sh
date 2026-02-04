#!/bin/bash
# Download All Hyperliquid APIs
# This script downloads all discovered API endpoints

BASE_DIR="$(pwd)/hyperliquid_data"
mkdir -p "$BASE_DIR"

echo "🚀 Hyperliquid API Downloader"
echo "============================="
echo ""

# Define all endpoints
declare -a ENDPOINTS=(
  "leaderboard:https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
  "largest_user_depositors:https://d2v1fiwobg9w6.cloudfront.net/largest_user_depositors"
  "largest_liquidated_notional_by_user:https://d2v1fiwobg9w6.cloudfront.net/largest_liquidated_notional_by_user"
  "largest_user_trade_count:https://d2v1fiwobg9w6.cloudfront.net/largest_user_trade_count"
  "largest_users_by_usd_volume:https://d2v1fiwobg9w6.cloudfront.net/largest_users_by_usd_volume"
  "cumulative_inflow:https://d2v1fiwobg9w6.cloudfront.net/cumulative_inflow"
  "daily_inflow:https://d2v1fiwobg9w6.cloudfront.net/daily_inflow"
)

TOTAL=0
SUCCESS=0

for endpoint in "${ENDPOINTS[@]}"; do
    NAME=$(echo "$endpoint" | cut -d':' -f1)
    URL=$(echo "$endpoint" | cut -d':' -f2-)
    OUTPUT="$BASE_DIR/${NAME}.json"
    
    echo "📥 Downloading: $NAME"
    if curl -sL "$URL" -o "$OUTPUT" 2>/dev/null; then
        SIZE=$(du -h "$OUTPUT" | cut -f1)
        echo "  ✅ $OUTPUT ($SIZE)"
        ((SUCCESS++))
    else
        echo "  ❌ Failed"
    fi
    ((TOTAL++))
    echo ""
done

echo "============================="
echo "📊 Downloaded: $SUCCESS/$TOTAL"
echo "📁 Location: $BASE_DIR"
