# Bitcoin Magazine Pro Metrics API

## ⚠️ Authentication Required

This API endpoint requires a valid Bitcoin Magazine Pro Professional Plan subscription.

## Endpoint
```
GET https://api.bitcoinmagazinepro.com/metrics
```

## Request Headers
```http
Authorization: Bearer YOUR_API_KEY
```

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hourly` | integer | No | Set to `1` to return only hourly metrics |

## Request Example
```bash
curl -X GET "https://api.bitcoinmagazinepro.com/metrics?hourly=1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Response Format

Returns a JSON array with metric names.

## Response Example (with Authentication)
```json
{
  "metrics": [
    {
      "name": "investor-tool",
      "category": "Market Cycle",
      "description": "Bitcoin Investor Tool: 2-Year MA Multiplier"
    },
    {
      "name": "200wma-heatmap",
      "category": "Market Cycle",
      "description": "200 Week Moving Average Heatmap"
    },
    {
      "name": "stock-to-flow",
      "category": "Market Cycle",
      "description": "Stock-to-Flow Model"
    }
  ]
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique metric identifier |
| `category` | string | Metric category (Market Cycle, Onchain, etc.) |
| `description` | string | Human-readable description |

## Usage Example
```python
import requests

def list_metrics(api_key, hourly=False):
    url = "https://api.bitcoinmagazinepro.com/metrics"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"hourly": "1"} if hourly else {}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    return response.json()

# List all metrics
metrics = list_metrics("your-api-key")
for metric in metrics:
    print(f"- {metric['name']}: {metric['description']}")
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | Required (Bearer Token) |
| **Response Format** | JSON |
| **Public Access** | ❌ No |
| **Subscription Required** | Professional Plan |

## ⚠️ Limitations
- Requires Professional Plan subscription
- Rate limits apply based on subscription tier
- Some metrics only available with higher tiers

## 💡 Use Cases
- Discovering available metrics
- Building metric catalogs
- Filtering metrics by type (hourly vs daily)

## Notes
- Use this endpoint to discover all available metrics before querying specific ones
- The `hourly` parameter filters to metrics that support hourly data updates

## Alternative Free Options
- CoinGecko API: https://www.coingecko.com/
- CryptoCompare API: https://www.cryptocompare.com/
