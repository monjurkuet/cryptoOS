# Fear & Greed Index

## Endpoint
```
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/fear_and_greed/_dash-layout
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/fear_and_greed/_dash-dependencies
POST https://www.bitcoinmagazinepro.com/django_plotly_dash/app/fear_and_greed/_dash-update-component
```

## Description
Multifactorial market sentiment analysis index for Bitcoin. Combines multiple data sources to determine market fear/greed levels.

## Inputs
| Input ID | Property | Values |
|----------|----------|--------|
| url | pathname | /charts/bitcoin-fear-and-greed-index/ |
| display | children | (display component) |

## Response Structure
```json
{
  "props": {
    "children": [
      {
        "props": {
          "id": "chart",
          "config": {
            "displayModeBar": false
          }
        }
      }
    ]
  }
}
```

## ⚠️ Limitations
- Requires authentication
- HTTP 500 without valid session

## 💡 Use Cases
- Market sentiment analysis
- Identifying buying opportunities (fear)
- Identifying selling opportunities (greed)

## Public Widget
A free widget is available:
```
https://www.bitcoinmagazinepro.com/widget/fear-and-greed/
```
