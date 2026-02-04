#!/bin/bash
# ⚠️ Bitcoin Magazine Pro API - Requires Authentication
# This script template requires a valid API key to function

# Configuration
API_BASE_URL="https://api.bitcoinmagazinepro.com"
API_KEY="${BITCOINMAGAZINEPRO_API_KEY:-}"

# Create data directory
mkdir -p data

# Function to download a metric
download_metric() {
    local metric_name=$1
    local output_file="data/${metric_name}.csv"

    echo "📥 Downloading ${metric_name}..."

    if [ -z "$API_KEY" ]; then
        echo "❌ ERROR: API key not set!"
        echo "Please set BITCOINMAGAZINEPRO_API_KEY environment variable or add your API key"
        echo "Get your API key from: https://www.bitcoinmagazinepro.com/api/"
        return 1
    fi

    curl -s -X GET "${API_BASE_URL}/metrics/${metric_name}" \
        -H "Authorization: Bearer ${API_KEY}" \
        -o "${output_file}"

    if [ -s "${output_file}" ]; then
        echo "✅ Saved to ${output_file}"
        ls -lh "${output_file}"
    else
        echo "❌ Failed to download ${metric_name}"
        rm -f "${output_file}"
    fi
}

# Check for API key
if [ -z "$API_KEY" ]; then
    echo "🔑 Bitcoin Magazine Pro API Key Required"
    echo "======================================"
    echo ""
    echo "The Bitcoin Magazine Pro API requires authentication."
    echo "Please follow these steps:"
    echo ""
    echo "1. Subscribe to Professional Plan: https://www.bitcoinmagazinepro.com/subscribe/"
    echo "2. Get your API key: https://www.bitcoinmagazinepro.com/api/"
    echo "3. Set your API key:"
    echo "   export BITCOINMAGAZINEPRO_API_KEY='your-api-key-here'"
    echo ""
    echo "Or create a .env file in the project root:"
    echo "   BITCOINMAGAZINEPRO_API_KEY=your-api-key-here"
    echo ""
    echo "📚 Documentation: https://www.bitcoinmagazinepro.com/api/docs/"
    echo ""
    echo "Available metrics include:"
    echo "  - Market Cycle: investor-tool, 200wma-heatmap, stock-to-flow, fear-and-greed"
    echo "  - Onchain: mvrv-zscore, nupl, rhodl-ratio, sopr"
    echo "  - Mining: puell-multiple, hashrate-ribbons, miner-difficulty"
    echo "  - And 100+ more metrics..."
    echo ""
    exit 1
fi

echo "🚀 Bitcoin Magazine Pro Data Download"
echo "======================================"
echo ""
echo "Base URL: ${API_BASE_URL}"
echo "Data directory: data/"
echo ""

# Download metrics (example list - add more as needed)
METRICS=(
    "investor-tool"
    "200wma-heatmap"
    "stock-to-flow"
    "fear-and-greed"
    "pi-cycle-top"
    "golden-ratio"
    "mvrv-zscore"
    "rhodl-ratio"
    "nupl"
    "reserve-risk"
    "hodl-waves"
    "hodl-1y"
    "puell-multiple"
    "hashrate-ribbons"
    "active-addresses"
)

echo "Downloading ${#METRICS[@]} metrics..."
echo ""

for metric in "${METRICS[@]}"; do
    download_metric "$metric"
    echo ""
done

echo "✅ All downloads completed!"
echo ""
echo "Files saved in data/:"
ls -lh data/
