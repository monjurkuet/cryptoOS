# Coin Metrics API

## Endpoint
```
GET https://community-api.coinmetrics.io/v4/timeseries/asset-metrics
```

## Request Body/Parameters
```json
None - GET request with query parameters
```

| Parameter | Type | Description | Required | Default |
|-----------|------|-------------|----------|---------|
| `assets` | string | Asset identifier(s) | Yes | - |
| `metrics` | string | Metrics to retrieve | Yes | - |
| `frequency` | string | Data frequency | No | `1d` |
| `start_time` | string | Start date/time | No | - |
| `end_time` | string | End date/time | No | - |
| `page_size` | integer | Results per page | No | 10,000 |
| `paging_from` | string | Pagination direction | No | `start` |
| `sort` | string | Sort order | No | `time` |
| `null_as_zero` | boolean | Null handling | No | `true` |

## Available Assets
- `btc` - Bitcoin
- `eth` - Ethereum
- Other cryptocurrencies

## Available Metrics

### Price Metrics
- `PriceUSD` - Price in USD
- `PriceBTC` - Price in BTC
- `CapMrktCurUSD` - Current market cap (USD)

### Blockchain Metrics
- `BlkCnt` - Block count
- `BlkSizeByte` - Block size (bytes)
- `TxCnt` - Transaction count
- `TxTfrValAdjUSD` - Transaction value (USD)
- `FeeTotUSD` - Total fees (USD)
- `FeeMeanNtv` - Mean fee (native units)
- `FeeMedianNtv` - Median fee (native units)

### Supply Metrics
- `SplyCur` - Current supply
- `IssTotNtv` - Total issuance (native units)
- `IssTotUSD` - Total issuance (USD)
- `IssCnt` - Issuance count

### Other Metrics
- `HashRate` - Hash rate
- `Difficulty` - Mining difficulty
- `ActiveCnt` - Active addresses
- `TxCnt` - Transaction count
- And many more...

## Description
Coin Metrics Community API provides free access to comprehensive blockchain and market data for major cryptocurrencies. It's a reliable secondary data source for Bitcoin on-chain analysis.

## Response Format
```json
{
  "data": [
    {
      "asset": "btc",
      "time": "2026-01-30T00:00:00.000000000Z",
      "PriceUSD": "84017.0340292227"
    },
    {
      "asset": "btc",
      "time": "2026-01-31T00:00:00.000000000Z",
      "PriceUSD": "78702.38550263"
    }
  ],
  "next_page_token": "0.MjAyNi0wMS0zMFQwMDowMDowMFo",
  "next_page_url": "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?..."
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `data` | array | Array of data points |
| `data[].asset` | string | Asset identifier |
| `data[].time` | string | Timestamp (ISO 8601) |
| `data[].PriceUSD` | string | Price in USD (example metric) |
| `next_page_token` | string | Pagination token for next page |
| `next_page_url` | string | URL for next page |

## Data Details

- **Frequency Options:** `1s` (seconds), `1m` (minutes), `1h` (hours), `1d` (days), `1w` (weeks)
- **Start Date:** 2009-01-03 (for Bitcoin)
- **Last Updated:** Present
- **Page Size:** Maximum 10,000 records

## Usage
```bash
# Get Bitcoin price data
curl -X GET "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD&frequency=1d&start_time=2025-01-01&page_size=100" \
  -H "Content-Type: application/json" \
  -o "data/coinmetrics_btc.json"

# Get multiple metrics
curl -X GET "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=PriceUSD,BlkCnt,TxCnt&frequency=1d&start_time=2025-01-01" \
  -o "data/coinmetrics_multi.json"
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None (Community API) |
| **Rate Limit** | Unknown |
| **Response Size** | ~8.7 KB (100 records) |
| **Status** | ✅ Working |
| **Data Points** | Unlimited (paginated) |

## ⚠️ Limitations
- Community API has lower rate limits than Pro API
- Page size limited to 10,000 records
- Some advanced metrics require Pro API
- Pagination required for large datasets

## 💡 Use Cases
- Historical price analysis
- Blockchain activity metrics
- Supply and issuance tracking
- Fee analysis
- Cross-asset comparison
- Backtesting and research

## Notes
- Free tier available with registration
- Pro API provides more metrics and higher limits
- Data is authoritative and widely used
- Supports multiple programming languages via HTTP
