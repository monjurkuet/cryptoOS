# CryptoQuant GraphQL Query Examples

## Complete Query Examples for All Categories

---

## 1. BTC Summary Query

```graphql
query {
  btc {
    summary {
      price {
        value
        change24h
        change7d
      }
      marketCap {
        value
        change24h
      }
      volume24h {
        value
        change24h
      }
      circulatingSupply {
        value
      }
    }
    marketIndicator {
      mvrvRatio {
        value
        change24h
        change7d
        timestamp
      }
    }
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
    }
    derivatives {
      fundingRate {
        value
        change24h
      }
      openInterest {
        value
        change24h
      }
    }
  }
}
```

---

## 2. Market Indicators Query

```graphql
query {
  btc {
    marketIndicator {
      mvrvRatio {
        value
        change24h
        change7d
        history(limit: 365) {
          timestamp
          value
          change24h
        }
      }
      estimatedLeverageRatio {
        value
        change24h
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
        history(limit: 90) {
          timestamp
          value
        }
      }
      futuresTakerCVD {
        value
        status
      }
      spotVolumeBubbleMap {
        status
        data {
          priceLevel
          volume
          color
        }
      }
      futuresVolumeBubbleMap {
        status
      }
      spotRetailActivity {
        status
        value
      }
      futuresRetailActivity {
        status
        value
      }
    }
    networkIndicator {
      sopr {
        value
        change24h
      }
      lthSopR {
        value
        change24h
      }
      sthSopR {
        value
        change24h
      }
      aSopR {
        value
        change24h
      }
      soprRatio {
        value
        change24h
      }
    }
  }
}
```

---

## 3. Exchange Flows Query

```graphql
query {
  btc {
    exchangeFlows {
      exchangeReserve {
        value
        unit
        change24h
        change7d
        timestamp
        history(limit: 365) {
          timestamp
          value
        }
      }
      exchangeNetflow {
        value
        unit
        change24h
        timestamp
        history(limit: 100) {
          timestamp
          value
        }
      }
      exchangeInflow {
        value
        unit
        change24h
      }
      exchangeOutflow {
        value
        unit
        change24h
      }
      whaleRatio {
        value
        change24h
      }
      inflowTop30 {
        address
        value
        timestamp
      }
      outflowTop30 {
        address
        value
        timestamp
      }
      exchangeReserveByExchange {
        exchange
        value
      }
      spotInflow {
        value
        change24h
      }
      derivativesInflow {
        value
        change24h
      }
    }
  }
}
```

---

## 4. Derivatives Query

```graphql
query {
  btc {
    derivatives {
      fundingRate {
        value
        change24h
        unit
        timestamp
        history(limit: 100) {
          timestamp
          value
        }
      }
      openInterest {
        value
        unit
        change24h
        timestamp
        history(limit: 100) {
          timestamp
          value
        }
      }
      longShortRatio {
        longRatio
        shortRatio
        netPosition
        history(limit: 100) {
          timestamp
          longRatio
          shortRatio
        }
      }
      takerVolume {
        buyVolume
        sellVolume
        netVolume
        history(limit: 100) {
          timestamp
          buyVolume
          sellVolume
        }
      }
      topTraderRatio {
        longRatio
        shortRatio
      }
      perpetualFunding {
        history(limit: 100) {
          timestamp
          rate
          exchange
        }
      }
      liquidations {
        longLiquidations
        shortLiquidations
        history(limit: 100) {
          timestamp
          longAmount
          shortAmount
        }
      }
      optionsOi {
        callOi
        putOi
        totalOi
      }
      basis {
        value
        history(limit: 100) {
          timestamp
          value
        }
      }
      volumeByExchange {
        exchange
        volume
      }
    }
  }
}
```

---

## 5. Fund Data Query

```graphql
query {
  btc {
    fundData {
      coinbasePremium {
        value
        change24h
        change7d
        timestamp
        history(limit: 100) {
          timestamp
          value
        }
      }
      coinbasePremiumGap {
        value
        change24h
      }
      koreaPremium {
        value
        change24h
        history(limit: 100) {
          timestamp
          value
        }
      }
      stablecoinSupplyRatio {
        value
        change24h
      }
      marketCap {
        value
        change24h
        unit
        history(limit: 365) {
          timestamp
          value
        }
      }
      realizedCap {
        value
        change24h
        unit
        history(limit: 365) {
          timestamp
          value
        }
      }
      averageCap {
        value
        change24h
      }
      deltaCap {
        value
        change24h
      }
      thermoCap {
        value
        change24h
      }
      priceVolume {
        ohlcv(limit: 100) {
          timestamp
          open
          high
          low
          close
          volume
        }
      }
      priceVolumeKrw {
        ohlcv(limit: 100) {
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

---

## 6. Network Stats Query

```graphql
query {
  btc {
    networkStats {
      activeAddresses {
        value
        change24h
        history(limit: 100) {
          timestamp
          value
        }
      }
      transactionCount {
        value
        change24h
      }
      transactionVolume {
        value
        unit
        change24h
      }
      utxoAgeBands {
        band
        percentage
        change7d
      }
      exchangeInteractionRate {
        value
        change24h
      }
      whaleTransactionCount {
        value
        change24h
      }
      newAddresses {
        value
        change24h
      }
      largeTransactionVolume {
        value
        change24h
      }
      realizedVolume {
        value
        change24h
      }
      zeroBalanceAddresses {
        value
        change24h
      }
    }
  }
}
```

---

## 7. Miner Flows Query

```graphql
query {
  btc {
    minerFlows {
      minerReserve {
        value
        change24h
      }
      minerInflow {
        value
        change24h
      }
      minerOutflow {
        value
        change24h
      }
      minerNetflow {
        value
        change24h
      }
      minerRevenue {
        value
        unit
        change24h
      }
    }
  }
}
```

---

## 8. Supply Query

```graphql
query {
  btc {
    supply {
      circulatingSupply {
        value
        percentage
      }
      burnedSupply {
        value
        percentage
      }
      reserveRisk {
        value
        change24h
      }
      marketCapToThermocap {
        value
        change24h
      }
      puellMultiple {
        value
        change24h
      }
    }
  }
}
```

---

## Python Example

```python
import requests

API_KEY = "your_api_key_here"
URL = "https://graph.cryptoquant.com/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

QUERY = """
query {
  btc {
    summary {
      price {
        value
        change24h
      }
      marketCap {
        value
      }
    }
    marketIndicator {
      mvrvRatio {
        value
        change24h
      }
    }
    exchangeFlows {
      exchangeReserve {
        value
      }
    }
    derivatives {
      fundingRate {
        value
      }
      openInterest {
        value
      }
    }
  }
}
"""

response = requests.post(URL, json={"query": QUERY}, headers=HEADERS)
data = response.json()

print(data)
```

---

## JavaScript Example

```javascript
const fetch = require('node-fetch');

const API_KEY = 'your_api_key_here';
const URL = 'https://graph.cryptoquant.com/graphql';

const query = `
query {
  btc {
    summary {
      price {
        value
        change24h
      }
    }
    marketIndicator {
      mvrvRatio {
        value
        change24h
      }
    }
  }
}
`;

fetch(URL, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  },
  body: JSON.stringify({ query })
})
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```

---

## Bash/Curl Example

```bash
#!/bin/bash
API_KEY="your_api_key_here"
URL="https://graph.cryptoquant.com/graphql"

curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "query { btc { summary { price { value change24h } marketIndicator { mvrvRatio { value change24h } } } } }"
  }' | jq '.'
```

---

## Error Handling

```javascript
// Check for errors
const response = await fetch(URL, options);
const result = await response.json();

if (result.errors) {
  console.error('GraphQL Errors:', result.errors);
}

if (!result.data) {
  console.error('No data returned');
}

// Common errors:
// - "Unauthorized": Invalid or missing API key
// - "Rate limited": Too many requests
// - "Not found": Invalid metric name
```

---

## Pagination & Limits

```graphql
// Get last 365 data points
history(limit: 365) {
  timestamp
  value
}

// Get data from specific date range
history(startDate: "2024-01-01", endDate: "2024-12-31") {
  timestamp
  value
}
```
