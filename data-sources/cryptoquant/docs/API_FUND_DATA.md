# CryptoQuant Fund Data APIs

## Overview
Fund data includes market capitalization models, premium indices, and stablecoin metrics.

## Available Endpoints

### 1. Coinbase Premium Index
**URL**: `/asset/btc/chart/fund-data/coinbase-premium`  
**Current**: -0.1435 (-57.44%)  
**Description**: % difference between Coinbase Pro (USD) and Binance (USDT) prices

### 2. Coinbase Premium Gap
**URL**: `/asset/btc/chart/fund-data/coinbase-premium-gap`  
**Current**: -108.72 (-51.33%)  
**Description**: Absolute price gap in USD

### 3. Korea Premium Index
**URL**: `/asset/btc/chart/fund-data/korea-premium`  
**Current**: 1.7199 (-33.5%)  
**Description**: Price premium on Korean exchanges

### 4. Stablecoin Supply Ratio (SSR)
**URL**: `/asset/btc/chart/fund-data/stablecoin-supply-ratio`  
**Description**: Stablecap / BTC Market Cap

### 5. Market Cap
**URL**: `/asset/btc/chart/fund-data/market-cap`  
**Current**: 1.5104T (-4.02%)  
**Description**: Total market capitalization

### 6. Realized Cap
**URL**: `/asset/btc/chart/fund-data/realized-cap`  
**Current**: 1.1128T (-0.18%)  
**Description**: Stored value (UTXOs at last move price)

### 7. Average Cap
**URL**: `/asset/btc/chart/fund-data/average-cap`  
**Current**: 343.6212B (+0.05%)  
**Description**: Moving average of market cap

### 8. Delta Cap
**URL**: `/asset/btc/chart/fund-data/delta-cap`  
**Current**: 769.2189B (-0.28%)  
**Description**: Realized Cap - Average Cap

### 9. Thermo Cap
**URL**: `/asset/btc/chart/fund-data/thermo-cap`  
**Current**: 90.9761B (+0.04%)  
**Description**: Miner inflows cap (total paid to miners)

### 10. Price & Volume (USD)
**URL**: `/asset/btc/chart/fund-data/price-volume`  
**Description**: OHLCV candlestick data

### 11. Price & Volume (KRW)
**URL**: `/asset/btc/chart/fund-data/price-volume-krw`  
**Description**: Korean market OHLCV

---

## API Usage

### GraphQL Query
```graphql
query {
  btc {
    fundData {
      coinbasePremium {
        value
        change24h
        change7d
      }
      koreaPremium {
        value
        change24h
      }
      marketCap {
        value
        change24h
        unit
      }
      realizedCap {
        value
        change24h
      }
      stablecoinSupplyRatio {
        value
        change24h
      }
      priceVolume {
        ohlcv {
          timestamp
          open
          high
          low
          close
          volume
        }
      }
    }
  }
}
```

### Download Script
```bash
#!/bin/bash
# Download all fund data metrics

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/fund_data"

mkdir -p "$OUTPUT_DIR"

metrics=(
    "coinbase-premium"
    "coinbase-premium-gap"
    "korea-premium"
    "stablecoin-supply-ratio"
    "market-cap"
    "realized-cap"
    "average-cap"
    "delta-cap"
    "thermo-cap"
    "price-volume"
    "price-volume-krw"
)

for metric in "${metrics[@]}"; do
    echo "📥 Downloading $metric..."
    curl -s -X POST "https://graph.cryptoquant.com/graphql" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "{\"query\":\"query { btc { fundData { ${metric} { value change24h change7d } } } }\"}" \
        -o "$OUTPUT_DIR/${metric}.json"
    echo "✅ Saved to $OUTPUT_DIR/${metric}.json"
done

echo ""
echo "🎉 All fund data downloaded!"
ls -lh "$OUTPUT_DIR"/*.json
```

---

## Response Format
```json
{
  "data": {
    "btc": {
      "fundData": {
        "coinbasePremium": {
          "value": -0.1435,
          "change24h": -57.44,
          "change7d": -23.1,
          "unit": "percent"
        },
        "marketCap": {
          "value": 1510400000000,
          "change24h": -4.02,
          "unit": "USD"
        },
        "realizedCap": {
          "value": 1112800000000,
          "change24h": -0.18,
          "unit": "USD"
        }
      }
    }
  }
}
```

---

## Interpretation Guide

| Metric | High Value Means | Low Value Means |
|--------|-----------------|-----------------|
| Coinbase Premium | US buying pressure | US selling pressure |
| Korea Premium | Korean buying pressure | - |
| SSR | More stablecoin buying power | Less buying power |
| MVRV (Cap/Cap) | Overvalued | Undervalued |
| Delta Cap | Market bottom signal | - |

---

## Use Cases

1. **US market sentiment**: Coinbase Premium Index
2. **Korean retail**: Korea Premium Index
3. **Buying power**: Stablecoin Supply Ratio
4. **Market cycles**: MVRV ratio (Market/Realized Cap)
5. **Volume analysis**: OHLCV candlestick data
