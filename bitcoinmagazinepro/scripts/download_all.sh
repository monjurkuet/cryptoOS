#!/bin/bash
# ⚠️ Bitcoin Magazine Pro Chart Downloader
# ⚠️ Requires authentication - WILL NOT WORK without login credentials
# This script documents the API structure for reference only

echo "=============================================="
echo "Bitcoin Magazine Pro Chart API Documentation"
echo "=============================================="
echo ""
echo "⚠️  WARNING: All endpoints require authentication"
echo "⚠️  This script documents the structure but cannot download data"
echo ""

# Create data directory
mkdir -p data

# Display all discovered endpoints
echo "📊 DISCOVERED CHART ENDPOINTS"
echo "================================"
echo ""

CATEGORIES=(
  "Market Cycle"
  "Onchain Indicators"
  "Onchain Movement"
  "Address Balance"
  "Mining"
  "Lightning Network"
  "Derivatives"
)

declare -A MARKET_CYCLE=(
  ["Bitcoin Investor Tool"]="market_cycle_ma"
  ["200 Week MA Heatmap"]="200wma_heatmap"
  ["Stock-to-Flow"]="stock_flow"
  ["Fear & Greed Index"]="fear_and_greed"
  ["Pi Cycle Top"]="pi_cycle_top_indicator"
  ["Golden Ratio"]="golden_ratio"
  ["Profitable Days"]="profitable_day"
  ["Rainbow Chart"]="rainbow"
  ["Pi Cycle Prediction"]="pi_cycle_top_e"
  ["Power Law"]="power_law"
)

declare -A ONCHAIN_INDICATORS=(
  ["MVRV Z-Score"]="mvrv_z"
  ["RHODL Ratio"]="rhodl_ratio"
  ["NUPL"]="unreali"
  ["Reserve Risk"]="re"
  ["Realized Price"]="realized_price"
  ["VDD Multiple"]="vdd_multiple"
  ["CVDD"]="cvdd"
  ["Top Cap"]="top_cap"
  ["Delta Top"]="delta_top"
  ["Balanced Price"]="balanced_price"
  ["Terminal Price"]="terminal_price"
  ["LTH Realized"]="realized_price_lth"
  ["STH Realized"]="realized_price_"
)

declare -A ONCHAIN_MOVEMENT=(
  ["HODL Waves"]="hodl_wave"
  ["5Y HODL Wave"]="hodl_wave_5y"
  ["10Y HODL Wave"]="hodl_wave_10y"
  ["Realized Cap HODL"]="rcap_hodl_wave"
  ["Whale Shadows"]="whale_watching"
  ["Coin Days Destroyed"]="bdd"
  ["Supply Adjusted CDD"]="bdd_"
  ["LTH Supply"]="lth_"
  ["Circulating Supply"]="circulating_"
)

declare -A ADDRESS_BALANCE=(
  ["Active Addresses"]="active_addre"
  ["> 0.01 BTC"]="min_001_count"
  ["> 0.1 BTC"]="min_01_count"
  ["> 1 BTC"]="min_1_count"
  ["> 10 BTC"]="min_10_count"
  ["> 100 BTC"]="min_100_count"
  ["> 1,000 BTC"]="min_1000_count"
  ["> 10,000 BTC"]="min_10000_count"
  ["Non-zero"]="min_0_count"
  ["New Addresses"]="new_addre"
)

declare -A MINING=(
  ["Puell Multiple"]="puell_multiple"
  ["Hash Ribbons"]="ha"
  ["Miner Difficulty"]="miner_difficulty"
  ["Miner Revenue Total"]="miner_revenue_total"
  ["Miner Revenue Block"]="miner_revenue_block_reward"
  ["Miner Revenue Fees"]="miner_revenue_fee"
)

declare -A LIGHTNING=(
  ["Lightning Capacity"]="lightning_capacity"
  ["Lightning Nodes"]="lightning_node"
)

declare -A DERIVATIVES=(
  ["Open Interest"]="open_intere"
  ["Funding Rates"]="funding_rate"
)

print_category() {
  local name=$1
  shift
  local -A map=("$@")
  echo "📈 $name"
  echo "-------------------------------------------"
  for chart in "${!map[@]}"; do
    app="${map[$chart]}"
    echo "  • $chart: /django_plotly_dash/app/$app/"
  done
  echo ""
}

print_category "Market Cycle" "${MARKET_CYCLE[@]}"
print_category "Onchain Indicators" "${ONCHAIN_INDICATORS[@]}"
print_category "Onchain Movement" "${ONCHAIN_MOVEMENT[@]}"
print_category "Address Balance" "${ADDRESS_BALANCE[@]}"
print_category "Mining" "${MINING[@]}"
print_category "Lightning Network" "${LIGHTNING[@]}"
print_category "Derivatives" "${DERIVATIVES[@]}"

echo ""
echo "📝 API ENDPOINTS"
echo "=============================================="
echo ""
echo "1. Get Chart Layout:"
echo "   GET /django_plotly_dash/app/{app}/_dash-layout"
echo ""
echo "2. Get Dependencies:"
echo "   GET /django_plotly_dash/app/{app}/_dash-dependencies"
echo ""
echo "3. Update Component:"
echo "   POST /django_plotly_dash/app/{app}/_dash-update-component"
echo ""

echo "⚠️  AUTHENTICATION REQUIRED"
echo "=============================================="
echo ""
echo "All endpoints require:"
echo "  • Professional Plan subscription"
echo "  • Valid session cookies"
echo "  • Django authentication"
echo ""
echo "Without authentication, requests return HTTP 500."
echo ""

echo "📚 DOCUMENTATION"
echo "=============================================="
echo ""
echo "Full documentation available in:"
echo "  • docs/API_INDEX.md"
echo "  • docs/API_*.md (individual endpoint docs)"
echo ""
echo "For free Bitcoin data alternatives, see README.md"
echo ""

echo "✅ Script completed (no data downloaded - auth required)"
