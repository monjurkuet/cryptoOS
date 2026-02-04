# Hyperliquid Staking APIs

## Endpoints
```
POST https://api.hyperliquid.xyz/info
```

## Request Bodies

### Staking Balance
```json
{
  "type": "stakingBalance",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Staking History
```json
{
  "type": "stakingHistory",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Staking Unstakeable
```json
{
  "type": "stakingUnstakeable",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns HYPE token staking information for a user.

## Response Format (Balance)
```json
{
  "staked": "10000.0",
  "unstakeable": "1000.0"
}
```

## Response Format (History)
```json
[
  {
    "type": "stake",
    "amount": "10000.0",
    "time": 1704067200000
  }
]
```

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"stakingBalance","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"stakingHistory","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"stakingUnstakeable","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## Use Cases

- Display staking balance
- Track staking history
- Monitor unstakeable tokens

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
