#!/bin/bash
# Explore all cryptoquant BTC pages and subpages

mkdir -p ~/development/cryptodata/cryptoquant/explored

# Main category pages
categories=(
    "summary"
    "exchange-flows"
    "market-indicator"
    "network-indicator"
    "miner-flows"
    "derivatives"
    "fund-data"
    "market-data"
    "addresses"
    "fees-and-revenue"
    "network-stats"
    "supply"
    "transactions"
    "inter-entity-flows"
    "research"
)

# Exchange Flows subpages
exchange_flows=(
    "exchange-reserve"
    "exchange-inflow"
    "exchange-outflow"
    "exchange-netflow"
    "inflow-top30"
    "outflow-top30"
    "whale-ratio"
    "exchange-reserve-by-exchange"
)

# Market Indicator subpages
market_indicators=(
    "mvrv-ratio"
    "estimated-leverage-ratio"
    "spot-average-order-size"
    "futures-average-order-size"
    "spot-taker-cvd"
    "futures-taker-cvd"
    "spot-volume-bubble-map"
    "futures-volume-bubble-map"
    "retail-activity"
)

# Derivatives subpages
derivatives=(
    "funding-rate"
    "open-interest"
    "long-short-ratio"
    "taker-buy-sell-volume"
)

# Fund Data subpages
fund_data=(
    "coinbase-premium"
    "korea-premium"
    "stablecoin-supply-ratio"
)

# Network Indicator subpages
network_indicators=(
    "sopr"
    "lth-sopr"
    "sth-sopr"
    "utxo-age-bands"
)

# Miner Flows subpages
miner_flows=(
    "miner-reserve"
    "miner-inflow"
    "miner-outflow"
    "miner-netflow"
)

echo "Creating exploration script..."
