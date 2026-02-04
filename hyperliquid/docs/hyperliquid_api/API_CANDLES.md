# Hyperliquid Candles API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "candles",
  "coin": "BTC",
  "interval": "1h",
  "startTime": 1704067200000
}
```

## Description
Returns OHLC candle data for a specific perpetual coin.

## Response Format
```json
[
  {
    "t": 1704067200000,
    "o": "75000.0",
    "h": "75500.0",
    "l": "74500.0",
    "c": "75200.0",
    "v": "1500.5"
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `t` | number | Timestamp (milliseconds) |
| `o` | string | Open price |
| `h` | string | High price |
| `l` | string | Low price |
| `c` | string | Close price |
| `v` | string | Volume |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"candles","coin":"BTC","interval":"1h","startTime":1704067200000}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~100-500 KB |

## Intervals

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `1h` | 1 hour |
| `4h` | 4 hours |
| `1d` | 1 day |

## Use Cases

- Chart price history
- Technical analysis
- Backtesting

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
