# Bitcoin Magazine Pro API - Puell Multiple

## Endpoint
```
POST https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-update-component
```

## Request Body
```json
{
  "output": "chart.figure",
  "outputs": [{"id": "chart", "property": "figure"}],
  "inputs": [
    {"id": "url", "property": "pathname", "value": "/charts/puell-multiple/"},
    {"id": "display", "property": "children"}
  ],
  "state": []
}
```

## Description
The Puell Multiple measures daily miner revenue relative to its 365-day moving average. It helps identify market cycle tops and bottoms by comparing current issuance value to historical norms.

## Fields

| Field | Type | Description |
|-------|------|-------------|
| data[].x | array | Dates |
| data[].y | array | Puell Multiple values |
| data[].type | string | "scatter" |
| data[].mode | string | "lines" |
| layout.title | string | "Puell Multiple" |

## Usage
```bash
curl -X POST "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-update-component" \
  -H "Content-Type: application/json" \
  -d '{"output":"chart.figure","outputs":[{"id":"chart","property":"figure"}],"inputs":[{"id":"url","property":"pathname"},{"id":"display","property":"children"}],"state":[]}'
```

## ⚠️ Limitations
- Requires authentication (returns 500 without session)
- Needs valid Django session cookies

## 💡 Use Cases
- Identifying mining revenue cycles
- Long-term accumulation signals
- Market cycle analysis

## Related Charts
- Miner Revenue Total
- Miner Revenue Fees
- Miner Difficulty
- Hash Ribbons
