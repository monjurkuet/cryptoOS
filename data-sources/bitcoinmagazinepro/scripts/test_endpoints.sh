#!/bin/bash
# Test Bitcoin Magazine Pro API endpoints
# ⚠️ Will fail without authentication - for documentation only

echo "=============================================="
echo "Bitcoin Magazine Pro API Endpoint Tester"
echo "=============================================="
echo ""
echo "⚠️  Testing endpoints WITHOUT authentication"
echo "⚠️  Expected result: HTTP 500 Server Error"
echo ""

ENDPOINTS=(
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/market_cycle_ma/_dash-layout"
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/200wma_heatmap/_dash-layout"
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/fear_and_greed/_dash-layout"
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/mvrv_z/_dash-layout"
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/puell_multiple/_dash-layout"
  "https://www.bitcoinmagazinepro.com/django_plotly_dash/app/hodl_wave/_dash-layout"
)

for endpoint in "${ENDPOINTS[@]}"; do
  echo "Testing: $endpoint"
  echo "-------------------------------------------"
  status=$(curl -s -o /dev/null -w "%{http_code}" "$endpoint")
  echo "Status: $status"
  if [ "$status" -eq 500 ]; then
    echo "Result: ❌ Server Error (expected - auth required)"
  elif [ "$status" -eq 200 ]; then
    echo "Result: ✅ Success (unexpected!)"
  else
    echo "Result: ⚠️ Status $status"
  fi
  echo ""
done

echo "=============================================="
echo "Public Widget Test"
echo "=============================================="
echo ""

widget="https://www.bitcoinmagazinepro.com/widget/fear-and-greed/"
echo "Testing: $widget"
echo "-------------------------------------------"
status=$(curl -s -o /dev/null -w "%{http_code}" "$widget")
echo "Status: $status"
if [ "$status" -eq 200 ]; then
  echo "Result: ✅ Public widget available"
  echo "Widget is embeddable JavaScript (not raw data API)"
else
  echo "Result: ⚠️ Status $status"
fi

echo ""
echo "=============================================="
echo "Test Complete"
echo "=============================================="
echo ""
echo "Conclusion:"
echo "  • All chart APIs require authentication"
echo "  • Only public widget is Fear & Greed embed"
echo "  • No free raw data APIs available"
echo ""
echo "For free Bitcoin data, consider:"
echo "  • CoinGecko API (coingecko.com)"
echo "  • CryptoCompare API (cryptocompare.com)"
echo "  • Blockchain.info (blockchain.com)"
