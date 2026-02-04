# Hyperliquid Vaults API

## Endpoint
```
https://stats-data.hyperliquid.xyz/Mainnet/vaults
```

## Description
Returns list of all 9,007 Hyperliquid vaults with performance metrics, TVL, and leader information.

## Response Format
```json
[
  {
    "apr": 0.0,
    "pnls": [
      ["day", ["0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0"]],
      ["week", ["0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0"]],
      ["month", ["0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0", "0.0"]],
      ["allTime", ["0.0", "-4022.69", "12539.38", "9492.36", "6034.20", "1826.30", "260.08"]]
    ],
    "summary": {
      "name": "Snipe Trading",
      "vaultAddress": "0x00043d4a2c258892172dc6ce5f62e2e3936ae0dc",
      "leader": "0x9ab020fd91d6909e3d0cbf6c078f8b8163836c06",
      "tvl": "0.000016",
      "isClosed": true,
      "relationship": { "type": "normal" },
      "createTimeMillis": 1736422051357
    }
  }
]
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `summary.name` | string | Vault display name |
| `summary.vaultAddress` | string | Vault contract address (Ethereum) |
| `summary.leader` | string | Vault leader's wallet address |
| `summary.tvl` | string | Total Value Locked in USD (can be very small) |
| `summary.isClosed` | boolean | Whether vault is closed to new users |
| `summary.relationship.type` | string | Relationship type (usually "normal") |
| `summary.createTimeMillis` | number | Vault creation timestamp (epoch ms) |
| `apr` | number | Annual Percentage Rate (may be 0.0) |
| `pnls` | array | Array of [timeframe, pnl_array] pairs |

## Timeframes in PnL Array

| Timeframe | Array Length | Description |
|-----------|--------------|-------------|
| `day` | 13 | PnL for last 13 periods (likely hours) |
| `week` | 12 | PnL for last 12 periods (likely days) |
| `month` | 13 | PnL for last 13 periods (likely days) |
| `allTime` | Variable | Historical PnL time series |

## Usage
```bash
curl -sL "https://stats-data.hyperliquid.xyz/Mainnet/vaults" -o data/vaults.json
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Download Size** | 13 MB |
| **Total Records** | 9,007 vaults |
| **Pagination** | ❌ None (all vaults in single request) |
| **Content-Type** | application/json |
| **Authentication** | None required |

## ⚠️ Limitations

- **No filtering parameters** - returns all vaults
- **No pagination** - entire vault list in single request
- **Large response** - 13 MB, slow connections may timeout
- **PnL array format unclear** - exact time intervals not documented
- **Many vaults have zero TVL** - abandoned or new vaults

## 💡 Use Cases

- Analyze vault performance over time
- Identify top-performing vault leaders
- Study vault adoption and TVL trends
- Compare vault strategies (PnL consistency)
- Find closed vs open vault opportunities

## 📊 Sample Data

| Vault Name | Address | Leader | TVL | Status |
|------------|---------|--------|-----|--------|
| Snipe Trading | 0x0004...ae0dc | 0x9ab0...6c06 | 0.000016 | Closed |
| Example Vault | 0x1234... | 0x5678... | 100.50 | Open |

## Notes
- PnL arrays contain string values, not numbers
- TVL can be extremely small (near zero) for new/abandoned vaults
- `createTimeMillis` is Unix timestamp in milliseconds
- `isClosed` indicates if vault is accepting new users
- Not all vaults have meaningful trading history

## Data Source
Hyperliquid official stats endpoint (stats-data.hyperliquid.xyz)
