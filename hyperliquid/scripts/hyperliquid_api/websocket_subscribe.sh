#!/bin/bash
# Download Hyperliquid WebSocket Data (using websocat)

# Install websocat if not available:
# curl -sL https://github.com/vi/websocat/releases/download/v1.12.0/websocat.x86_64-unknown-linux-musl.gz | gunzip > /usr/local/bin/websocat
# chmod +x /usr/local/bin/websocat

WEBSOCKET_URL="wss://api.hyperliquid.xyz/trading"
CHANNEL="${1:-trades}"
COIN="${2:-BTC}"
INTERVAL="${3:-1h}"
OUTPUT_FILE="${4:-data/hyperliquid/ws_${CHANNEL}_${COIN}.jsonl}"
MAX_MESSAGES="${5:-100}"

echo "🔌 Connecting to WebSocket: $WEBSOCKET_URL"
echo "📡 Channel: $CHANNEL, Coin: $COIN, Interval: $INTERVAL"
echo "📁 Output: $OUTPUT_FILE"
echo ""

# Create subscription message
case $CHANNEL in
    trades)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"trades","coin":"'$COIN'"}}'
        ;;
    book)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"book","coin":"'$COIN'"}}'
        ;;
    candle)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"candle","coin":"'$COIN'","interval":"'$INTERVAL'"}}'
        ;;
    orderUpdates)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"orderUpdates"}}'
        ;;
    userFills)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"userFills"}}'
        ;;
    user)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"user"}}'
        ;;
    webData2)
        SUBSCRIPTION='{"type":"subscribe","subscription":{"type":"webData2"}}'
        ;;
    *)
        echo "Unknown channel: $CHANNEL"
        echo "Available: trades, book, candle, orderUpdates, userFills, user, webData2"
        exit 1
        ;;
esac

echo "Subscription: $SUBSCRIPTION"
echo ""

# Use websocat to subscribe and save to file
# Note: For authenticated endpoints, you'll need to sign a message
if command -v websocat &> /dev/null; then
    timeout 60 websocat -E -B 65535 "$WEBSOCKET_URL" \
        --text "$SUBSCRIPTION" \
        | head -n "$MAX_MESSAGES" \
        | tee "$OUTPUT_FILE"
else
    echo "websocat not found. Using curl to test WebSocket..."
    echo "Install websocat for full WebSocket support:"
    echo "  curl -sL https://github.com/vi/websocat/releases/download/v1.12.0/websocat.x86_64-unknown-linux-musl.gz | gunzip > /usr/local/bin/websocat"
    echo ""
    echo "Testing with Python websockets library instead..."
    python3 -c "
import asyncio
import json
import websockets

async def subscribe():
    async with websockets.connect('$WEBSOCKET_URL') as ws:
        await ws.send('$SUBSCRIPTION')
        for i in range(min($MAX_MESSAGES, 100)):
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            print(json.dumps(data, indent=2))
            with open('$OUTPUT_FILE', 'a') as f:
                f.write(json.dumps(data) + '\n')

asyncio.run(subscribe())
"
fi

echo ""
echo "✅ Saved to $OUTPUT_FILE"
ls -lh "$OUTPUT_FILE"
