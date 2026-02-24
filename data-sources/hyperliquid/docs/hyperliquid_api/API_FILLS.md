# Hyperliquid Fills API

## Endpoint
```
POST https://api.hyperliquid.xyz/info
```

## Request Body
```json
{
  "type": "fills",
  "user": "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"
}
```

## Description
Returns recent trade executions (fills) for a user.

## Response Format
```json
[
  {
    "coin": "ETH",
    "px": "2225.5",
    "sz": "0.225",
    "side": "B",
    "time": 1770163586470,
    "startPosition": "-544.4221",
    "dir": "Close Short",
    "closedPnl": "2.74275",
    "hash": "0xa9a512926554ef4fab1e0434a0dc100211a5007800580e214d6dbde52458c93a",
    "oid": 311060176177,
    "crossed": false,
    "fee": "-0.015022",
    "tid": 107411944047202,
    "cloid": "0x00dbc3f8259c01000000000000000000",
    "feeToken": "USDC",
    "twapId": null
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `coin` | string | Perpetual coin ticker |
| `px` | string | Execution price |
| `sz` | string | Trade size |
| `side` | string | Order side: "B" (Buy) or "A" (Ask/Sell) |
| `time` | number | Execution timestamp (milliseconds) |
| `startPosition` | string | Position size before trade |
| `dir` | string | Trade direction description |
| `closedPnl` | string | Closed PnL from this trade |
| `hash` | string | Transaction hash |
| `oid` | number | Order ID |
| `crossed` | boolean | Whether order crossed spread |
| `fee` | string | Trading fee (negative = rebate) |
| `tid` | number | Trade ID |
| `cloid` | string | Client order ID |
| `feeToken` | string | Token used for fee (USDC) |
| `twapId` | string \| null | TWAP order ID |

## Usage
```bash
curl -s -X POST "https://api.hyperliquid.xyz/info" \
  -H "Content-Type: application/json" \
  -d '{"type":"fills","user":"0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2"}'
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None required |
| **Response Size** | ~10-500 KB |

## Limitations

- Returns recent fills (last 1000+)
- Use v2/tradesHistory for more complete history

## Use Cases

- Track recent trading activity
- Calculate trading statistics
- Monitor PnL from closed positions

## Data Source

Hyperliquid Official API (api.hyperliquid.xyz)
