# CryptoQuant Market Indicator APIs

## Overview
Market indicators provide insight into market sentiment, whale behavior, and on-chain activity.

## Available Endpoints

### 1. MVRV Ratio
**Metric**: Market Cap / Realized Cap  
**URL**: `/asset/btc/chart/market-indicator/mvrv-ratio`  
**Description**: Indicates overvalued (>3.7) or undervalued (<1) market conditions  
**Current Value**: 1.3573

### 2. Estimated Leverage Ratio (ELR)
**URL**: `/asset/btc/chart/market-indicator/estimated-leverage-ratio`  
**Description**: Combined leverage of futures and margin markets

### 3. Spot Average Order Size
**URL**: `/asset/btc/chart/market-indicator/spot-average-order-size`  
**Description**: Average trade size on spot markets (whale indicator)

### 4. Futures Average Order Size
**URL**: `/asset/btc/chart/market-indicator/futures-average-order-size`  
**Description**: Average trade size on derivatives markets

### 5. Spot Taker CVD (90-day)
**URL**: `/asset/btc/chart/market-indicator/spot-taker-cvd`  
**Description**: Cumulative Volume Delta (buy volume - sell volume)  
**Status**: Taker Buy Dominant

### 6. Futures Taker CVD (90-day)
**URL**: `/asset/btc/chart/market-indicator/futures-taker-cvd`  
**Description**: Derivatives market volume delta  
**Status**: Taker Buy Dominant

### 7. Spot Volume Bubble Map
**URL**: `/asset/btc/chart/market-indicator/spot-volume-bubble-map`  
**Description**: Visual representation of volume by price level  
**Status**: Neutral

### 8. Futures Volume Bubble Map
**URL**: `/asset/btc/chart/market-indicator/futures-volume-bubble-map`  
**Description**: Derivatives volume visualization  
**Status**: Neutral

### 9. Spot Retail Activity
**URL**: `/asset/btc/chart/market-indicator/spot-retail-activity`  
**Description**: Trading frequency surge indicator  
**Status**: Neutral

### 10. Futures Retail Activity
**URL**: `/asset/btc/chart/market-indicator/futures-retail-activity`  
**Description**: Derivatives retail participation  
**Status**: Neutral

### 11. SOPR
**URL**: `/asset/btc/chart/network-indicator/sopr`  
**Description**: Spent Output Profit Ratio - profit/loss on spent outputs

### 12. LTH-SOPR
**URL**: `/asset/btc/chart/network-indicator/lth-sopr`  
**Description**: Long-Term Holder SOPR

### 13. STH-SOPR
**URL**: `/asset/btc/chart/network-indicator/sth-sopr`  
**Description**: Short-Term Holder SOPR

### 14. aSOPR
**URL**: `/asset/btc/chart/network-indicator/asopr`  
**Description**: Adjusted SOPR (excludes <1h UTXOs)

### 15. SOPR Ratio
**URL**: `/asset/btc/chart/network-indicator/sopr-ratio`  
**Description**: LTH-SOPR/STH-SOPR ratio

---

## API Usage

### GraphQL Query
```graphql
query {
  btc {
    marketIndicator {
      mvrvRatio {
        value
        change24h
        change7d
      }
      spotAverageOrderSize {
        value
        change24h
      }
      futuresAverageOrderSize {
        value
        change24h
      }
      spotTakerCVD {
        value
        status
      }
      futuresTakerCVD {
        value
        status
      }
    }
  }
}
```

### Download Script
```bash
#!/bin/bash
# Download all market indicators

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/market_indicators"

mkdir -p "$OUTPUT_DIR"

indicators=(
    "mvrv-ratio"
    "estimated-leverage-ratio"
    "spot-average-order-size"
    "futures-average-order-size"
    "spot-taker-cvd"
    "futures-taker-cvd"
    "spot-volume-bubble-map"
    "futures-volume-bubble-map"
    "spot-retail-activity"
    "futures-retail-activity"
)

for indicator in "${indicators[@]}"; do
    echo "📥 Downloading $indicator..."
    curl -s -X POST "https://graph.cryptoquant.com/graphql" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "{\"query\":\"query { btc { marketIndicator { ${indicator} { value change24h change7d } } } }\"}" \
        -o "$OUTPUT_DIR/${indicator}.json"
    echo "✅ Saved to $OUTPUT_DIR/${indicator}.json"
done

echo ""
echo "🎉 All market indicators downloaded!"
ls -lh "$OUTPUT_DIR"/*.json
```

---

## Response Format

### Individual Indicator
```json
{
  "data": {
    "btc": {
      "marketIndicator": {
        "mvrvRatio": {
          "value": 1.3573,
          "change24h": -3.85,
          "change7d": -12.4,
          "timestamp": "2026-02-04T12:00:00Z"
        }
      }
    }
  }
}
```

### Time Series
```json
{
  "data": {
    "btc": {
      "marketIndicator": {
        "mvrvRatio": {
          "history": [
            {
              "timestamp": "2026-02-04T00:00:00Z",
              "value": 1.3573,
              "change24h": -3.85
            }
          ]
        }
      }
    }
  }
}
```

---

## Use Cases

1. **MVRV Ratio**: Identify market tops (>3.7) and bottoms (<1)
2. **Average Order Size**: Detect whale accumulation/distribution
3. **Taker CVD**: Gauge buying vs selling pressure
4. **Volume Bubble Map**: Identify price levels with high volume
5. **Retail Activity**: Track retail participation spikes
