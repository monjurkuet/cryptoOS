#!/bin/bash
# Download ALL APIs from CBBI

echo "🚀 Downloading ALL data from CBBI..."

# Create directories
mkdir -p data/cbbi data/coinank data/coinmetrics

# Download CBBI main data
echo "  📄 CBBI main data..."
./scripts/download_cbbi.sh

# Download Coinank indicator data
echo ""
echo "  📄 Coinank MVRV Z-Score..."
./scripts/download_mvrv_zscore.sh

echo "  📄 Coinank Reserve Risk..."
./scripts/download_reserve_risk.sh

echo "  📄 Coinank RHODL Ratio..."
./scripts/download_rhodl_ratio.sh

# Download Coin Metrics data
echo ""
echo "  📄 Coin Metrics BTC price..."
./scripts/download_coinmetrics.sh

echo ""
echo "✅ All data downloaded!"
echo ""
echo "📊 Downloaded files:"
ls -lh data/cbbi/ data/coinank/ data/coinmetrics/
