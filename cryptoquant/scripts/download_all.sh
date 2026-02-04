#!/bin/bash
# Download ALL CryptoQuant Data
# Requires: CRYPTOQUANT_API_KEY environment variable

set -e

echo "🚀 CryptoQuant Data Downloader"
echo "================================"
echo ""

# Check for API key
if [ -z "${CRYPTOQUANT_API_KEY}" ]; then
    echo "⚠️  ERROR: CRYPTOQUANT_API_KEY not set!"
    echo "Please set your API key:"
    echo "  export CRYPTOQUANT_API_KEY='your_api_key_here'"
    echo ""
    echo "Get free API key from: https://cryptoquant.com"
    exit 1
fi

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data"

mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/market_indicators"
mkdir -p "$OUTPUT_DIR/exchange_flows"
mkdir -p "$OUTPUT_DIR/derivatives"
mkdir -p "$OUTPUT_DIR/fund_data"
mkdir -p "$OUTPUT_DIR/network"
mkdir -p "$OUTPUT_DIR/miner_flows"
mkdir -p "$OUTPUT_DIR/addresses"
mkdir -p "$OUTPUT_DIR/fees_revenue"
mkdir -p "$OUTPUT_DIR/supply"
mkdir -p "$OUTPUT_DIR/transactions"

echo "📥 Downloading Market Indicators..."
# MVRV Ratio
curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { marketIndicator { mvrvRatio { value change24h change7d } estimatedLeverageRatio { value change24h } spotAverageOrderSize { value change24h } futuresAverageOrderSize { value change24h } spotTakerCVD { value status } futuresTakerCVD { value status } } } }"}' \
    -o "$OUTPUT_DIR/market_indicators/mvrv_ratio.json"

echo "✅ Market Indicators"

echo "📥 Downloading Exchange Flows..."
curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { exchangeFlows { exchangeReserve { value change24h } exchangeNetflow { value change24h } exchangeInflow { value change24h } exchangeOutflow { value change24h } whaleRatio { value change24h } } } }"}' \
    -o "$OUTPUT_DIR/exchange_flows/exchange_flows.json"

echo "✅ Exchange Flows"

echo "📥 Downloading Derivatives..."
curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { derivatives { fundingRate { value change24h } openInterest { value change24h } longShortRatio { longRatio shortRatio } takerVolume { buyVolume sellVolume } } } }"}' \
    -o "$OUTPUT_DIR/derivatives/derivatives.json"

echo "✅ Derivatives"

echo "📥 Downloading Fund Data..."
curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { fundData { coinbasePremium { value change24h } koreaPremium { value change24h } marketCap { value change24h } realizedCap { value change24h } stablecoinSupplyRatio { value change24h } } } }"}' \
    -o "$OUTPUT_DIR/fund_data/fund_data.json"

echo "✅ Fund Data"

echo ""
echo "🎉 All data downloaded successfully!"
echo ""
echo "📁 Output directory: $OUTPUT_DIR"
echo ""
ls -lh "$OUTPUT_DIR"/*/
