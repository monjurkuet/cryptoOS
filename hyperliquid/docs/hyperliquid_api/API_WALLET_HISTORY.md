# Hyperliquid Wallet & History APIs

## Endpoints
```
POST https://api.hyperliquid.xyz/info
```

## Request Bodies

### Wallet
```json
{
  "type": "wallet",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Ledger
```json
{
  "type": "ledger",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Deposit History
```json
{
  "type": "depositHistory",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

### Withdraw History
```json
{
  "type": "withdrawHistory",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns wallet balances and transaction history for a user.

## Response Format (Wallet)
```json
{
  "address": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2",
  "balances": []
}
```

## Response Format (Ledger)
```json
[
  {
    "type": "deposit",
    "amount": "10000.0",
    "hash": "0x...",
    "time": 1704067200000
  }
]
```

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"wallet","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"ledger","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"depositHistory","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'

curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"withdrawHistory","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## Use Cases

- Display wallet balances
- Track deposits and withdrawals
- Monitor transaction history

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
