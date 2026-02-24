# Hyperliquid Vaults API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "vaults"
}
```

## Description
Returns list of all available vaults on Hyperliquid.

## Response Format
```json
[
  {
    "name": "Example Vault",
    "vaultAddress": "0x...",
    "tvls": [
      { "t": 1704067200000, "tv": "1000000.0" }
    ]
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Vault name |
| `vaultAddress` | string | Vault contract address |
| `tvls` | array | TVL history [timestamp, value] |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"vaults"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~50-200 KB |

## Use Cases

- List available vaults
- Analyze vault performance
- Monitor vault TVL

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
