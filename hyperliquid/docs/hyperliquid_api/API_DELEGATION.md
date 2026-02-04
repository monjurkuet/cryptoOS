# Hyperliquid Delegation APIs

## Endpoints
```
POST https://api.hyperliquid.xyz/info
```

## Request Bodies

### Delegation Balance
```json
{
  "type": "delegationBalance",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Delegation History
```json
{
  "type": "delegationHistory",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns HYPE token delegation information for a user.

## Response Format (Balance)
```json
{
  "delegated": "5000.0",
  "rewards": "100.0"
}
```

## Response Format (History)
```json
[
  {
    "type": "delegate",
    "amount": "5000.0",
    "validator": "0x...",
    "time": 1704067200000
  }
]
```

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"delegationBalance","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"delegationHistory","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## Use Cases

- Display delegation balance
- Track delegation rewards
- Monitor validator performance

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
