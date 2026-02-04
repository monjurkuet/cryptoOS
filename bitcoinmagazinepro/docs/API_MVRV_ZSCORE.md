# MVRV Z-Score

## Endpoint
```
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/mvrv_z/_dash-layout
GET https://www.bitcoinmagazinepro.com/django_plotly_dash/app/mvrv_z/_dash-dependencies
POST https://www.bitcoinmagazinepro.com/django_plotly_dash/app/mvrv_z/_dash-update-component
```

## Description
Market Value to Realized Value (MVRV) Z-Score. Pulls apart differences between market value and realized value to identify market cycle highs and lows.

## Formula
```
MVRV Z-Score = (Market Cap - Realized Cap) / StdDev(Realized Cap)
```

## ⚠️ Limitations
- Requires authentication
- HTTP 500 without valid session

## 💡 Use Cases
- Identifying market tops (high values)
- Identifying market bottoms (low/negative values)
- Long-term trend analysis

## Related Metrics
- STH MVRV Z-Score
- LTH MVRV Z-Score
- MVRV Z-Score 2YR Rolling
