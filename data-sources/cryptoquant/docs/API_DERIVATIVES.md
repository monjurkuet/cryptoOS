# CryptoQuant Derivatives APIs

## Overview
Derivatives data tracks futures and options markets, including funding rates, open interest, and liquidations.

## Available Endpoints

### 1. Funding Rates
**URL**: `/asset/btc/chart/derivatives/funding-rate`  
**Current**: 0.005561 (+423.19%)  
**Description**: Perpetual contract funding rates (per 8h)

### 2. Open Interest
**URL**: `/asset/btc/chart/derivatives/open-interest`  
**Current**: 23.8622B (-1.73%)  
**Description**: Total value of open positions

### 3. Long/Short Ratio
**URL**: `/asset/btc/chart/derivatives/long-short-ratio`  
**Description**: Net positioning (longs vs shorts)

### 4. Taker Buy/Sell Volume
**URL**: `/asset/btc/chart/derivatives/taker-volume`  
**Description**: Market buy vs sell volume on derivatives

### 5. Top Trader Long/Short
**URL**: `/asset/btc/chart/derivatives/top-trader-ratio`  
**Description**: Professional trader positioning

### 6. Perpetual Funding
**URL**: `/asset/btc/chart/derivatives/perpetual-funding`  
**Description**: Detailed funding rate history

### 7. Liquidations
**URL**: `/asset/btc/chart/derivatives/liquidations`  
**Description**: Long and short liquidation amounts

### 8. Options Open Interest
**URL**: `/asset/btc/chart/derivatives/options-oi`  
**Description**: Options market open interest

### 9. Basis
**URL**: `/asset/btc/chart/derivatives/basis`  
**Description**: Futures premium/discount to spot

### 10. Volume by Exchange
**URL**: `/asset/btc/chart/derivatives/volume-by-exchange`  
**Description**: Trading volume per exchange

---

## API Usage

### GraphQL Query
```graphql
query {
  btc {
    derivatives {
      fundingRate {
        value
        change24h
        perpsHistory {
          timestamp
          rate
        }
      }
      openInterest {
        value
        change24h
        unit
      }
      longShortRatio {
        longRatio
        shortRatio
        netPosition
      }
      takerVolume {
        buyVolume
        sellVolume
        netVolume
      }
    }
  }
}
```

### Download Script
```bash
#!/bin/bash
# Download all derivatives metrics

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/derivatives"

mkdir -p "$OUTPUT_DIR"

metrics=(
    "funding-rate"
    "open-interest"
    "long-short-ratio"
    "taker-volume"
    "top-trader-ratio"
    "perpetual-funding"
    "liquidations"
    "options-oi"
    "basis"
    "volume-by-exchange"
)

for metric in "${metrics[@]}"; do
    echo "📥 Downloading $metric..."
    curl -s -X POST "https://graph.cryptoquant.com/graphql" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "{\"query\":\"query { btc { derivatives { ${metric} { value change24h } } } }\"}" \
        -o "$OUTPUT_DIR/${metric}.json"
    echo "✅ Saved to $OUTPUT_DIR/${metric}.json"
done

echo ""
echo "🎉 All derivatives data downloaded!"
ls -lh "$OUTPUT_DIR"/*.json
```

---

## Response Format
```json
{
  "data": {
    "btc": {
      "derivatives": {
        "fundingRate": {
          "value": 0.005561,
          "change24h": 423.19,
          "unit": "rate",
          "timestamp": "2026-02-04T12:00:00Z"
        },
        "openInterest": {
          "value": 23862200000,
          "change24h": -1.73,
          "unit": "USD"
        }
      }
    }
  }
}
```

---

## Interpretation Guide

| Metric | Bullish Signal | Bearish Signal |
|--------|---------------|----------------|
| Funding Rate | High positive (>0.01%) | Negative |
| Open Interest | Rising (new money) | Falling (closing) |
| Long/Short Ratio | >1 (more longs) | <1 (more shorts) |
| Taker Buy Vol > Sell Vol | Buyers aggressive | Sellers aggressive |
| Liquidations (Longs) | Squeeze incoming | - |
| Liquidations (Shorts) | - | Squeeze incoming |

---

## Use Cases

1. **Funding rate analysis**: Identify market sentiment and overleveraged positions
2. **Open Interest tracking**: Detect new money entering or exiting
3. **Liquidation levels**: Predict price levels with high leverage
4. **Basis trading**: Identify futures vs spot arbitrage opportunities
5. **Top trader tracking**: Follow smart money positioning
