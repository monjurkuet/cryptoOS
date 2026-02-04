#!/bin/bash
# Test all CloudFront endpoints

ENDPOINTS=(
  "cumulative_inflow"
  "daily_inflow"
  "cumulative_usd_volume"
  "open_interest"
  "funding_rate"
  "cumulative_trades"
  "daily_usd_volume"
  "daily_unique_users"
  "daily_notional_liquidated_by_coin"
  "liquidity_by_coin"
  "cumulative_new_users"
  "largest_user_depositors"
  "largest_liquidated_notional_by_user"
  "largest_user_trade_count"
  "largest_users_by_usd_volume"
)

BASE_URL="https://d2v1fiwobg9w6.cloudfront.net"

for ep in "${ENDPOINTS[@]}"; do
  URL="${BASE_URL}/${ep}"
  HTTP_CODE=$(curl -sI "$URL" | grep "HTTP" | tail -1 | awk '{print $2}')
  if [ "$HTTP_CODE" == "200" ]; then
    SIZE=$(curl -sI "$URL" | grep "Content-Length" | awk '{print $2}' | tr -d '\r')
    echo "✅ $ep - $HTTP_CODE - $SIZE"
  else
    echo "❌ $ep - $HTTP_CODE"
  fi
done
