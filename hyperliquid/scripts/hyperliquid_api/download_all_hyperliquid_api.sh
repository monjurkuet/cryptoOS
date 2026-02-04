#!/bin/bash
# Download ALL Hyperliquid API data for a user

set -e

USER_ADDRESS="${1:-0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2}"
OUTPUT_DIR="data/hyperliquid"
mkdir -p "$OUTPUT_DIR"

API_URL="https://api.hyperliquid.xyz/info"

echo "🚀 Downloading ALL Hyperliquid API Data"
echo "======================================"

echo ""
echo "👤 User Data..."
echo "  📊 clearinghouseState..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"clearinghouseState\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/clearinghouse_state.json"

echo "  📋 openOrders..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"openOrders\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/open_orders.json"

echo "  💰 fills..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"fills\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/fills.json"

echo "  📋 historicalOrders..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"historicalOrders\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/historical_orders.json"

echo "  💰 userFills..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userFills\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/user_fills.json"

echo "  💰 v2/tradesHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"v2/tradesHistory\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/trades_history_v2.json"

echo ""
echo "💵 Funding & Account..."
echo "  💸 userFunding..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userFunding\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/user_funding.json"

echo "  🏦 accountState..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"accountState\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/account_state.json"

echo "  📊 crossMarginSummary..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"crossMarginSummary\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/cross_margin_summary.json"

echo "  📈 effectiveLeverage..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"effectiveLeverage\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/effective_leverage.json"

echo ""
echo "💰 Wallet & History..."
echo "  💰 wallet..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"wallet\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/wallet.json"

echo "  📋 ledger..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"ledger\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/ledger.json"

echo "  💵 depositHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"depositHistory\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/deposit_history.json"

echo "  💸 withdrawHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"withdrawHistory\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/withdraw_history.json"

echo ""
echo "🪙 Spot Data..."
echo "  🪙 spotClearinghouseState..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"spotClearinghouseState\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/spot_clearinghouse_state.json"

echo "  🪙 spotOrders..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"spotOrders\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/spot_orders.json"

echo "  🪙 spotFills..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"spotFills\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/spot_fills.json"

echo ""
echo "🥩 Staking Data..."
echo "  🥩 stakingBalance..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"stakingBalance\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/staking_balance.json"

echo "  📜 stakingHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"stakingHistory\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/staking_history.json"

echo "  🥩 stakingUnstakeable..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"stakingUnstakeable\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/staking_unstakeable.json"

echo ""
echo "🥩 Delegation Data..."
echo "  🥩 delegationBalance..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"delegationBalance\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/delegation_balance.json"

echo "  📜 delegationHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"delegationHistory\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/delegation_history.json"

echo ""
echo "⭐ Points & Rewards..."
echo "  ⭐ userPoints..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userPoints\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/user_points.json"

echo "  💵 feeSchedule..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"feeSchedule\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/fee_schedule.json"

echo ""
echo "🏥 Health & Rate Limits..."
echo "  🏥 healthInfo..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"healthInfo\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/health_info.json"

echo "  📊 userRateLimit..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userRateLimit\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/user_rate_limit.json"

echo "  🐋 userWhale..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"type\":\"userWhale\",\"user\":\"$USER_ADDRESS\"}" \
  -o "$OUTPUT_DIR/user_whale.json"

echo ""
echo "🌐 Market Data (BTC)..."
echo "  📈 ticker..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"ticker","coin":"BTC"}' \
  -o "$OUTPUT_DIR/ticker_BTC.json"

echo "  📚 orderbook..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"orderbook","coin":"BTC"}' \
  -o "$OUTPUT_DIR/orderbook_BTC.json"

echo "  📊 l2Book..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"l2Book","coin":"BTC"}' \
  -o "$OUTPUT_DIR/l2book_BTC.json"

echo "  💸 fundingHistory..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"fundingHistory","coin":"BTC"}' \
  -o "$OUTPUT_DIR/funding_history_BTC.json"

echo "  📊 trades..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"trades","coin":"BTC"}' \
  -o "$OUTPUT_DIR/trades_BTC.json"

echo ""
echo "🌐 Global Data..."
echo "  🌐 metaAndAssetCtxs..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"metaAndAssetCtxs"}' \
  -o "$OUTPUT_DIR/meta_asset_ctxs.json"

echo "  💵 allMids..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"allMids"}' \
  -o "$OUTPUT_DIR/all_mids.json"

echo "  ⚠️ liquidationCandidates..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"liquidationCandidates"}' \
  -o "$OUTPUT_DIR/liquidation_candidates.json"

echo "  📊 recentTransactions..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"recentTransactions"}' \
  -o "$OUTPUT_DIR/recent_transactions.json"

echo "  🪙 spotMeta..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"spotMeta"}' \
  -o "$OUTPUT_DIR/spot_meta.json"

echo "  💵 spotMids..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"spotMids"}' \
  -o "$OUTPUT_DIR/spot_mids.json"

echo "  🏦 vaults..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"vaults"}' \
  -o "$OUTPUT_DIR/vaults.json"

echo "  🏆 leaderboard..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"leaderboard"}' \
  -o "$OUTPUT_DIR/leaderboard.json"

echo "  🌐 communityInfo..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"communityInfo"}' \
  -o "$OUTPUT_DIR/community_info.json"

echo "  ✅ exchangeStatus..."
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{"type":"exchangeStatus"}' \
  -o "$OUTPUT_DIR/exchange_status.json"

echo ""
echo "======================================"
echo "✅ All data downloaded to $OUTPUT_DIR/"
echo ""
echo "Total files: $(ls -1 "$OUTPUT_DIR"/*.json 2>/dev/null | wc -l)"
ls -lh "$OUTPUT_DIR"/*.json 2>/dev/null | awk '{print $5, $9}' | sort
