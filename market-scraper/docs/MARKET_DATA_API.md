# Market Data API Endpoints

## Current BTC Price

### Endpoint: `GET /api/v1/markets/{symbol}`

Returns the latest candle data for a symbol, which includes the current price.

```bash
curl http://localhost:8000/api/v1/markets/BTC
```

**Response:**
```json
{
  "symbol": "BTC",
  "latest_candle": {
    "t": "2026-02-19T10:30:00Z",
    "o": 96900.0,
    "h": 97100.0,
    "l": 96800.0,
    "c": 97050.0,
    "v": 150.5
  }
}
```

**Field Mapping:**
| Field | Meaning | Description |
|-------|---------|-------------|
| `t` | Timestamp | Candle start time (UTC) |
| `o` | Open | Opening price |
| `h` | High | Highest price in period |
| `l` | Low | Lowest price in period |
| `c` | Close | **Current/Latest price** |
| `v` | Volume | Trading volume in period |

**Getting Current Price:**
- Use `latest_candle.c` (close price) as the current price
- The 1-hour candle is used by default, providing a good balance of recency and stability

---

## Historical Candle Data

### Endpoint: `GET /api/v1/markets/{symbol}/history`

Returns historical OHLCV candlestick data.

```bash
# Basic query - last 100 1-hour candles
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h"

# With time range
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&start_time=2026-02-01T00:00:00&end_time=2026-02-19T00:00:00&limit=500"
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeframe` | string | `1h` | Candle interval: `1m`, `5m`, `15m`, `1h`, `4h`, `1d` |
| `start_time` | datetime | None | Start time (ISO 8601 format, inclusive) |
| `end_time` | datetime | None | End time (ISO 8601 format, inclusive) |
| `limit` | int | 100 | Max results (1-10,000) |

**Response:**
```json
{
  "symbol": "BTC",
  "timeframe": "1h",
  "candles": [
    {
      "t": "2026-02-19T08:00:00Z",
      "o": 96900.0,
      "h": 97050.0,
      "l": 96800.0,
      "c": 96950.0,
      "v": 120.3
    },
    {
      "t": "2026-02-19T09:00:00Z",
      "o": 96950.0,
      "h": 97100.0,
      "l": 96900.0,
      "c": 97000.0,
      "v": 135.7
    },
    {
      "t": "2026-02-19T10:00:00Z",
      "o": 97000.0,
      "h": 97150.0,
      "l": 96950.0,
      "c": 97050.0,
      "v": 150.5
    }
  ],
  "count": 3
}
```

---

## Available Timeframes

| Timeframe | Description | Use Case |
|-----------|-------------|----------|
| `1m` | 1 minute | Scalping, high-frequency analysis |
| `5m` | 5 minutes | Short-term trading signals |
| `15m` | 15 minutes | Intraday analysis |
| `1h` | 1 hour | **Default - General purpose** |
| `4h` | 4 hours | Swing trading |
| `1d` | 1 day | Long-term trend analysis |

---

## Query Examples

### Get Last 24 Hours of 1-Hour Candles

```bash
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&limit=24"
```

### Get Last 7 Days of Daily Candles

```bash
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1d&limit=7"
```

### Get Specific Date Range

```bash
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&start_time=2026-02-15T00:00:00&end_time=2026-02-19T00:00:00&limit=200"
```

### Get Last 100 5-Minute Candles for Scalping

```bash
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=5m&limit=100"
```

---

## Response Field Reference

### Candle Object

```json
{
  "t": "2026-02-19T10:00:00Z",  // Candle start timestamp (ISO 8601)
  "o": 97000.0,                 // Open price (USD)
  "h": 97150.0,                 // High price (USD)
  "l": 96950.0,                 // Low price (USD)
  "c": 97050.0,                 // Close price (USD) - use for price
  "v": 150.5                    // Volume (BTC)
}
```

### Derived Metrics (Calculate from OHLCV)

```python
# Price change (absolute)
change = candle["c"] - candle["o"]

# Price change (percentage)
change_pct = ((candle["c"] - candle["o"]) / candle["o"]) * 100

# Candle range (volatility)
range_ = candle["h"] - candle["l"]

# Average price
avg_price = (candle["h"] + candle["l"] + candle["c"]) / 3

# Volume-weighted estimation
vwap_estimate = (candle["h"] + candle["l"] + candle["c"]) / 3  # Approximate
```

---

## Data Source

All price data comes from **Hyperliquid** via WebSocket subscription to candle channels:

- **WebSocket URL**: `wss://api.hyperliquid.xyz/ws`
- **Subscription**: `{"method": "subscribe", "subscription": {"type": "candle", "coin": "BTC", "interval": "1h"}}`

Data is stored in MongoDB collections named:
- `btc_candles_1m`
- `btc_candles_5m`
- `btc_candles_15m`
- `btc_candles_1h`
- `btc_candles_4h`
- `btc_candles_1d`

---

## Common Use Cases

### 1. Get Current Price

```bash
# Simplest way to get current price
curl -s "http://localhost:8000/api/v1/markets/BTC" | jq '.latest_candle.c'
```

### 2. Calculate Price Change

```bash
# Get last 2 candles to calculate change
curl -s "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&limit=2" | jq '.candles'
```

### 3. Get 24-Hour Statistics

```bash
# Get 24 hourly candles and calculate stats
curl -s "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&limit=24"
```

From this you can calculate:
- 24h high (max of all `h` values)
- 24h low (min of all `l` values)
- 24h volume (sum of all `v` values)
- 24h price change (first `o` vs last `c`)

### 4. Get Historical Price at Specific Time

```bash
# Get candles around a specific time
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&start_time=2026-02-15T10:00:00&end_time=2026-02-15T12:00:00&limit=5"
```

---

## Error Responses

### Symbol Not Found

```bash
curl "http://localhost:8000/api/v1/markets/INVALID"
```

```json
{
  "detail": "Market INVALID not found"
}
```

**Status Code:** 404

### No Data Available

```bash
curl "http://localhost:8000/api/v1/markets/BTC/history?timeframe=1h&start_time=2030-01-01T00:00:00"
```

```json
{
  "symbol": "BTC",
  "timeframe": "1h",
  "candles": [],
  "count": 0
}
```

**Status Code:** 200 (empty result is valid)

---

## Rate Limits & Performance

- No API rate limits (self-hosted)
- Query performance optimized with MongoDB indexes on `t` (timestamp) field
- Maximum 10,000 candles per request
- Recommended to use appropriate `limit` to avoid large responses

---

## WebSocket Real-Time Updates

For real-time trader and signal updates, connect to WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws?channel=traders');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.event_type = 'position_update' or 'signal'
    console.log('Update:', data);
};
```

Available channels:
- `traders` - Trader position and score updates
- `signals` - Trading signal alerts

---

## Summary Table

| Need | Endpoint | Method |
|------|----------|--------|
| **Current price** | `/api/v1/markets/{symbol}` | Use `latest_candle.c` |
| **Historical prices** | `/api/v1/markets/{symbol}/history` | Use `candles[].c` |
| **Volume data** | `/api/v1/markets/{symbol}/history` | Use `candles[].v` |
| **Price range** | `/api/v1/markets/{symbol}/history` | Use `candles[].h` and `.l` |
| **OHLC data** | `/api/v1/markets/{symbol}/history` | Full candle data |
| **Real-time updates** | `/ws?channel=traders` | WebSocket |

---

*Last Updated: February 2026*
