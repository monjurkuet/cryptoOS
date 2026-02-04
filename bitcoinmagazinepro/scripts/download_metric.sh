#!/bin/bash
# Download Specific Bitcoin Magazine Pro Metric
# Requires: BITCOINMAGAZINEPRO_API_KEY environment variable

METRIC_NAME="${1:-}"
API_BASE_URL="https://api.bitcoinmagazinepro.com"
API_KEY="${BITCOINMAGAZINEPRO_API_KEY:-}"

if [ -z "$METRIC_NAME" ]; then
    echo "❌ Usage: $0 <metric_name>"
    echo ""
    echo "Example: $0 mvrv-zscore"
    echo "         $0 fear-and-greed"
    echo "         $0 investor-tool"
    echo ""
    echo "Available metric names:"
    echo "  Market Cycle: investor-tool, 200wma-heatmap, stock-to-flow, fear-and-greed,"
    echo "                pi-cycle-top, golden-ratio, profitable-days, rainbow-indicator,"
    echo "                pi-cycle-top-bottom, pi-cycle-top-prediction, power-law"
    echo "  Onchain:      mvrv-zscore, rhodl-ratio, nupl, reserve-risk,"
    echo "                active-address-sentiment, advanced-nvt-signal, realized-price,"
    echo "                vdd-multiple, cvdd, top-cap, delta-top, balanced-price,"
    echo "                terminal-price, lth-realized-price, sth-realized-price,"
    echo "                addresses-in-profit, addresses-in-loss, sopr,"
    echo "                short-term-holder-mvrv, long-term-holder-mvrv, everything-indicator"
    echo "  Onchain Move: hodl-waves, hodl-1y, hodl-5y, hodl-10y,"
    echo "                rcap-hodl-waves, whale-watching, bdd, bdd-supply-adjusted,"
    echo "                circulating-supply, long-term-holder-supply, short-term-holder-supply"
    echo "  Addresses:    active-addresses, wallets-001, wallets-01, wallets-1,"
    echo "                wallets-10, wallets-100, wallets-1000, wallets-10000,"
    echo "                wallets-1-usd, wallets-10-usd, wallets-100-usd,"
    echo "                wallets-1k-usd, wallets-10k-usd, wallets-100k-usd,"
    echo "                wallets-1m-usd, non-zero-addresses, new-addresses"
    echo "  Mining:        puell-multiple, hashrate-ribbons, miner-difficulty,"
    echo "                miner-revenue-total, miner-revenue-block-rewards,"
    echo "                miner-revenue-fees, miner-revenue-fees-pct,"
    echo "                block-height, blocks-mined, hashprice, hashprice-volatility"
    echo "  Lightning:    lightning-capacity, lightning-nodes"
    echo "  Derivatives:   fr-average, btc-open-interest"
    echo "  Macro:         high-yield-credit-vs-btc, pmi-vs-btc, m2-vs-btc-yoy,"
    echo "                m1-vs-btc-yoy, m2-global-vs-btc, fed-balance-sheet,"
    echo "                fed-target-rate, financial-stress-index-vs-btc"
    exit 1
fi

if [ -z "$API_KEY" ]; then
    echo "❌ ERROR: API key not set!"
    echo "Please set BITCOINMAGAZINEPRO_API_KEY environment variable"
    echo "Get your API key from: https://www.bitcoinmagazinepro.com/api/"
    exit 1
fi

OUTPUT_FILE="data/${METRIC_NAME}.csv"

echo "📥 Downloading ${METRIC_NAME}..."
curl -s -X GET "${API_BASE_URL}/metrics/${METRIC_NAME}" \
    -H "Authorization: Bearer ${API_KEY}" \
    -o "${OUTPUT_FILE}"

if [ -s "${OUTPUT_FILE}" ]; then
    echo "✅ Saved to ${OUTPUT_FILE}"
    ls -lh "${OUTPUT_FILE}"
    echo ""
    echo "First few lines:"
    head -5 "${OUTPUT_FILE}"
else
    echo "❌ Failed to download ${METRIC_NAME}"
    exit 1
fi
