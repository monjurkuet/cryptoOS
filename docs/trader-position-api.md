# Trader Position API Documentation

## Overview

The Trader Position API provides access to tracked trader data from Hyperliquid, including real-time position information for top traders.

## Important: Position Data Behavior

### WebSocket-Driven Updates

Position data is **only available when traders have open positions**. This is due to how Hyperliquid's WebSocket API works:

- Hyperliquid WebSocket only sends position updates when a trader **has an open position**
- When a trader closes all positions, updates stop flowing for that address
- Historical position data is retained, but no new updates are sent

### Position Status Values

The API returns a `position_status` field with the following values:

| Status | Description |
|--------|-------------|
| `long` | Trader has a long BTC position |
| `short` | Trader has a short BTC position |
| `flat` | Trader has no positions on record (either closed or never had any) |
| `unknown` | No position data has ever been received for this trader |

### Why Some Traders Show "unknown"

An `unknown` status indicates one of:

1. Trader was recently added to tracking and no position data has been received yet
2. WebSocket connection issues prevented data collection
3. Trader has never had an open position since tracking began

## API Endpoints

### List Traders

```
GET /api/v1/traders
```

Lists all tracked traders with their position status.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Maximum traders to return (1-500) |
| `min_score` | float | 0 | Minimum score filter |
| `tag` | string | null | Filter by tag (e.g., "whale", "consistent") |
| `has_positions` | bool | null | Filter by whether trader has positions |
| `position_status` | string | null | Filter by: flat, long, short, unknown |
| `updated_within_hours` | int | null | Only traders updated within N hours |

#### Response

```json
{
  "traders": [
    {
      "address": "0x...",
      "display_name": "Trader Name",
      "score": 85.5,
      "tags": ["whale", "consistent"],
      "account_value": 1500000.00,
      "active": true,
      "has_positions": true,
      "position_status": "long",
      "last_position_update": "2025-04-13T20:30:00Z"
    }
  ],
  "total": 287,
  "symbol": "BTC",
  "total_with_positions": 45,
  "total_flat": 99,
  "total_unknown": 143
}
```

### Get Trader Details

```
GET /api/v1/traders/{address}
```

Get detailed information for a specific trader.

#### Response

```json
{
  "address": "0x...",
  "display_name": "Trader Name",
  "score": 85.5,
  "tags": ["whale"],
  "account_value": 1500000.00,
  "active": true,
  "positions": [
    {
      "coin": "BTC",
      "size": 15.5,
      "entry_price": 84500.00,
      "mark_price": 85000.00,
      "unrealized_pnl": 7750.00,
      "leverage": 10.0
    }
  ],
  "last_updated": "2025-04-13T20:30:00Z",
  "position_status": "long",
  "has_positions": true,
  "btc_position": {
    "coin": "BTC",
    "size": 15.5,
    "entry_price": 84500.00,
    "mark_price": 85000.00,
    "unrealized_pnl": 7750.00,
    "leverage": 10.0
  }
}
```

## Common Use Cases

### Find traders with active BTC positions

```
GET /api/v1/traders?has_positions=true
```

### Find traders who recently updated

```
GET /api/v1/traders?updated_within_hours=24
```

### Find traders with long BTC positions

```
GET /api/v1/traders?position_status=long
```

### Find flat traders (no positions)

```
GET /api/v1/traders?position_status=flat
```

## Error Handling

The API uses standard HTTP status codes:

- `200` - Success
- `400` - Invalid request (e.g., malformed address)
- `404` - Trader not found
- `500` - Internal server error
- `503` - Service unavailable (repository not available)

## Rate Limits

No rate limits are currently enforced, but please be respectful of server resources.

## Data Freshness

Position data freshness depends on:

1. WebSocket connection health (check `/health/status` endpoint)
2. Whether the trader has an open position
3. Trading activity (more active traders update more frequently)

Check `last_position_update` to see when data was last received for a trader.
