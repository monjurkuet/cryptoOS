#!/bin/bash
# Test API Connectivity
# Usage: ./test_api.sh

echo "🔍 Testing CryptoQuant API Connectivity"
echo "=========================================="
echo ""

# Check API key
if [ -z "${CRYPTOQUANT_API_KEY}" ]; then
    echo "❌ CRYPTOQUANT_API_KEY not set"
    echo "Please set your API key first:"
    echo "  export CRYPTOQUANT_API_KEY='your_api_key'"
    exit 1
fi

API_KEY="${CRYPTOQUANT_API_KEY}"

echo "✅ API Key configured"
echo ""

# Test 1: GraphQL Endpoint
echo "🧪 Test 1: GraphQL Endpoint"
echo "------------------------------"
RESPONSE=$(curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { summary { mvrvRatio { value } } } }"}')

if echo "$RESPONSE" | grep -q "data"; then
    echo "✅ GraphQL endpoint accessible"
    echo "📄 Response: $(echo "$RESPONSE" | head -c 200)"
else
    echo "❌ GraphQL endpoint failed"
    echo "📄 Response: $RESPONSE"
fi
echo ""

# Test 2: BTC Summary
echo "🧪 Test 2: BTC Summary"
echo "------------------------"
RESPONSE=$(curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { summary { price { value change24h } marketCap { value } } } }"}')

if echo "$RESPONSE" | grep -q "data"; then
    echo "✅ BTC Summary accessible"
    echo "📄 Response: $(echo "$RESPONSE" | head -c 200)"
else
    echo "❌ BTC Summary failed"
fi
echo ""

# Test 3: Exchange Flows
echo "🧪 Test 3: Exchange Flows"
echo "---------------------------"
RESPONSE=$(curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { exchangeFlows { exchangeReserve { value } exchangeNetflow { value } } } }"}')

if echo "$RESPONSE" | grep -q "data"; then
    echo "✅ Exchange Flows accessible"
else
    echo "❌ Exchange Flows failed"
fi
echo ""

# Test 4: Derivatives
echo "🧪 Test 4: Derivatives"
echo "-----------------------"
RESPONSE=$(curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { derivatives { fundingRate { value } openInterest { value } } } }"}')

if echo "$RESPONSE" | grep -q "data"; then
    echo "✅ Derivatives accessible"
else
    echo "❌ Derivatives failed"
fi
echo ""

# Test 5: Fund Data
echo "🧪 Test 5: Fund Data"
echo "---------------------"
RESPONSE=$(curl -s -X POST "https://graph.cryptoquant.com/graphql" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d '{"query":"query { btc { fundData { coinbasePremium { value } marketCap { value } } } }"}')

if echo "$RESPONSE" | grep -q "data"; then
    echo "✅ Fund Data accessible"
else
    echo "❌ Fund Data failed"
fi
echo ""

echo "🎉 API Tests Complete!"
