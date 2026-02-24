# Hyperliquid All Mids API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "allMids"
}
```

## Description
Returns mark prices for all perpetual coins.

## Response Format
```json
{
  "BTC": "75579.5",
  "ETH": "2224.65",
  "SOL": "97.356",
  "HYPE": "0.54068"
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `COIN` | string | Mark price for each coin |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"allMids"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~2-5 KB |

## Use Cases

- Get all mark prices at once
- Calculate portfolio value
- Monitor price movements

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
