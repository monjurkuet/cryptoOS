# CryptoQuant Exchange Flows APIs

## Overview
Exchange flows track the movement of cryptocurrencies into and out of exchanges, indicating potential buying or selling pressure.

## Available Endpoints

### 1. Exchange Reserve
**URL**: `/asset/btc/chart/exchange-flows/exchange-reserve`  
**Current**: 2.7495M (+0.09%)  
**Description**: Total BTC held on all exchanges

### 2. Exchange Netflow
**URL**: `/asset/btc/chart/exchange-flows/exchange-netflow`  
**Current**: 2.5346K (-0.36%)  
**Description**: Inflow - Outflow. Positive = increasing reserves (selling pressure)

### 3. Exchange Inflow
**URL**: `/asset/btc/chart/exchange-flows/exchange-inflow`  
**Current**: 56.1724K (+0.96%)  
**Description**: Total coins flowing INTO exchanges (selling pressure)

### 4. Exchange Outflow
**URL**: `/asset/btc/chart/exchange-flows/exchange-outflow`  
**Description**: Coins leaving exchanges (withdrawals)

### 5. Exchange Whale Ratio
**URL**: `/asset/btc/chart/exchange-flows/whale-ratio`  
**Current**: 0.9767 (+1.03%)  
**Description**: Top 10 inflows / Total inflows. High = whale activity

### 6. Inflow Top30
**URL**: `/asset/btc/chart/exchange-flows/inflow-top30`  
**Description**: Largest incoming transfers (whale tracking)

### 7. Outflow Top30
**URL**: `/asset/btc/chart/exchange-flows/outflow-top30`  
**Description**: Largest outgoing transfers

### 8. Exchange Reserve by Exchange
**URL**: `/asset/btc/chart/exchange-flows/exchange-reserve-by-exchange`  
**Description**: Per-exchange reserves breakdown

### 9. Spot Inflow
**URL**: `/asset/btc/chart/exchange-flows/spot-inflow`  
**Description**: Inflows to spot exchanges only

### 10. Derivatives Inflow
**URL**: `/asset/btc/chart/exchange-flows/derivatives-inflow`  
**Description**: Inflows to derivatives/perp exchanges

---

## API Usage

### GraphQL Query
```graphql
query {
  btc {
    exchangeFlows {
      exchangeReserve {
        value
        change24h
        change7d
      }
      exchangeNetflow {
        value
        change24h
      }
      exchangeInflow {
        value
        change24h
      }
      exchangeOutflow {
        value
        change24h
      }
      whaleRatio {
        value
        change24h
      }
    }
  }
}
```

### Download Script
```bash
#!/bin/bash
# Download all exchange flow metrics

API_KEY="${CRYPTOQUANT_API_KEY}"
OUTPUT_DIR="data/exchange_flows"

mkdir -p "$OUTPUT_DIR"

metrics=(
    "exchange-reserve"
    "exchange-netflow"
    "exchange-inflow"
    "exchange-outflow"
    "whale-ratio"
    "inflow-top30"
    "outflow-top30"
    "exchange-reserve-by-exchange"
    "spot-inflow"
    "derivatives-inflow"
)

for metric in "${metrics[@]}"; do
    echo "📥 Downloading $metric..."
    curl -s -X POST "https://graph.cryptoquant.com/graphql" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d "{\"query\":\"query { btc { exchangeFlows { ${metric} { value change24h change7d } } } }\"}" \
        -o "$OUTPUT_DIR/${metric}.json"
    echo "✅ Saved to $OUTPUT_DIR/${metric}.json"
done

echo ""
echo "🎉 All exchange flow data downloaded!"
ls -lh "$OUTPUT_DIR"/*.json
```

---

## Response Format
```json
{
  "data": {
    "btc": {
      "exchangeFlows": {
        "exchangeReserve": {
          "value": 2749500,
          "unit": "BTC",
          "change24h": 0.09,
          "change7d": -1.23,
          "timestamp": "2026-02-04T12:00:00Z"
        },
        "exchangeNetflow": {
          "value": 2534.6,
          "unit": "BTC",
          "change24h": -0.36
        }
      }
    }
  }
}
```

---

## Interpretation Guide

| Metric | Rising | Falling |
|--------|--------|---------|
| Exchange Reserve | Selling pressure | Buying pressure |
| Netflow (Positive) | Reserves increasing | Reserves decreasing |
| Netflow (Negative) | Buying from cold storage | Selling to cold storage |
| Whale Ratio (>0.9) | Whales moving to exchanges | - |
| Inflow Spike | Potential selloff incoming | - |
| Outflow Spike | Accumulation | - |

---

## Use Cases

1. **Detect selling pressure**: Rising reserves + positive netflow
2. **Spot accumulation**: Declining reserves + negative netflow
3. **Whale tracking**: Monitor Top30 inflows/outflows
4. **Exchange health**: Compare reserves across exchanges
5. **Derivatives vs Spot**: Compare inflows to gauge leverage building
