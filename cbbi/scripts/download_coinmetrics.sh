#!/bin/bash
# Download Coin Metrics Data

API_URL="https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
OUTPUT_FILE="data/coinmetrics/btc_price.json"

echo "📥 Downloading Coin Metrics BTC price data..."
curl -s -X GET "$API_URL?assets=btc&metrics=PriceUSD&frequency=1d&start_time=2025-01-01&page_size=100" \
  -H "Content-Type: application/json" \
  -o "$OUTPUT_FILE"

echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
