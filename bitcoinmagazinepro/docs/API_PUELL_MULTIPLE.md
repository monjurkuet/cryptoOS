# Puell Multiple

## Endpoint
```
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-layout
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-dependencies
POST https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-update-component
```

## Description
Relationship between daily bitcoin issuance and price. Measures miner revenue relative to 365-day average.

## Formula
```
Puell Multiple = Daily Miner Revenue / 365-day Average Daily Revenue
```

## Interpretation
- **< 1.0**: Undervalued (good buying opportunity)
- **1.0 - 2.0**: Neutral
- **> 2.0**: Overvalued (potential top)

## ⚠️ Limitations
- Requires authentication
- HTTP 500 without valid session

## 💡 Use Cases
- Identifying mining profitability cycles
- Long-term accumulation opportunities
- Market cycle timing
