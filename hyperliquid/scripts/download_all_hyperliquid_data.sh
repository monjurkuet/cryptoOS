#!/bin/bash
# Download all Hyperliquid API data

set -e

OUTPUT_DIR="data"
mkdir -p "$OUTPUT_DIR"

echo "🚀 Downloading All Hyperliquid Data"
echo "=================================="

BASE_CLOUDFRONT="https://d2v1fiwobg9w6.cloudfront.net"
STATS_DATA="https://stats-data.hyperliquid.xyz"

# Market Data
echo ""
echo "📊 Market Data..."
curl -sL "${BASE_CLOUDFRONT}/cumulative_inflow" -o "${OUTPUT_DIR}/cumulative_inflow.json"
curl -sL "${BASE_CLOUDFRONT}/daily_inflow" -o "${OUTPUT_DIR}/daily_inflow.json"
curl -sL "${BASE_CLOUDFRONT}/cumulative_usd_volume" -o "${OUTPUT_DIR}/cumulative_usd_volume.json"
curl -sL "${BASE_CLOUDFRONT}/daily_usd_volume" -o "${OUTPUT_DIR}/daily_usd_volume.json"

# Trading Data (larger files)
echo ""
echo "📈 Trading Data (Open Interest, Funding Rate, etc.)..."
curl -sL "${BASE_CLOUDFRONT}/open_interest" -o "${OUTPUT_DIR}/open_interest.json"
curl -sL "${BASE_CLOUDFRONT}/funding_rate" -o "${OUTPUT_DIR}/funding_rate.json"
curl -sL "${BASE_CLOUDFRONT}/liquidity_by_coin" -o "${OUTPUT_DIR}/liquidity_by_coin.json"
curl -sL "${BASE_CLOUDFRONT}/daily_notional_liquidated_by_coin" -o "${OUTPUT_DIR}/daily_notional_liquidated_by_coin.json"

# User Data
echo ""
echo "👤 User Data..."
curl -sL "${BASE_CLOUDFRONT}/cumulative_trades" -o "${OUTPUT_DIR}/cumulative_trades.json"
curl -sL "${BASE_CLOUDFRONT}/daily_unique_users" -o "${OUTPUT_DIR}/daily_unique_users.json"
curl -sL "${BASE_CLOUDFRONT}/cumulative_new_users" -o "${OUTPUT_DIR}/cumulative_new_users.json"

# Rankings (Top 1,000)
echo ""
echo "🏆 Rankings (Top 1,000)..."
curl -sL "${BASE_CLOUDFRONT}/largest_user_depositors" -o "${OUTPUT_DIR}/largest_user_depositors.json"
curl -sL "${BASE_CLOUDFRONT}/largest_liquidated_notional_by_user" -o "${OUTPUT_DIR}/largest_liquidated_notional_by_user.json"
curl -sL "${BASE_CLOUDFRONT}/largest_user_trade_count" -o "${OUTPUT_DIR}/largest_user_trade_count.json"
curl -sL "${BASE_CLOUDFRONT}/largest_users_by_usd_volume" -o "${OUTPUT_DIR}/largest_users_by_usd_volume.json"

# Stats Data
echo ""
echo "👑 Stats Data (Leaderboard & Vaults)..."
curl -sL "${STATS_DATA}/Mainnet/leaderboard" -o "${OUTPUT_DIR}/leaderboard.json"
curl -sL "${STATS_DATA}/Mainnet/vaults" -o "${OUTPUT_DIR}/vaults.json"

echo ""
echo "=================================="
echo "✅ All data downloaded to ${OUTPUT_DIR}/"
ls -lh "$OUTPUT_DIR"/*.json 2>/dev/null | awk '{print $5, $9}' | sort
echo ""
echo "Total files: $(ls -1 "$OUTPUT_DIR"/*.json 2>/dev/null | wc -l)"
