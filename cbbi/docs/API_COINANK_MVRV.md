# Coinank MVRV Z-Score API

## Endpoint
```
GET https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/mvrv-zscore/
```

## Request Body/Parameters
```json
None - GET request with required query parameter
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `type` | string | Chart type selector | Yes |

## Description
Coinank API endpoint for MVRV Z-Score data. MVRV (Market Value to Realized Value) Z-Score is an on-chain metric that helps identify Bitcoin market cycles by comparing market capitalization to realized capitalization.

## Response Format
```json
{
  "code": 200,
  "success": true,
  "message": "成功",
  "data": {
    "weekList": [
      {
        "id": null,
        "value1": 1.593482980760586,
        "value2": 1782414598783.0894,
        "value3": 1118565193543.7205,
        "value4": 1.1225945801319441,
        "value5": null,
        "value6": null,
        "value7": null,
        "value8": null,
        "value9": null,
        "value10": null,
        "value11": null,
        "value12": null,
        "value13": null,
        "type": "/charts/mvrv-zscore/",
        "createTime": "2026-01-27",
        "btcPrice": null
      }
    ]
  }
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | integer | Response status code (200 = success) |
| `success` | boolean | Success indicator |
| `message` | string | Response message (Chinese: "成功" = Success) |
| `data.weekList` | array | Array of weekly data points |
| `weekList[].value1` | float | MVRV Z-Score primary value |
| `weekList[].value2` | float | Market Cap (USD) |
| `weekList[].value3` | float | Realized Cap (USD) |
| `weekList[].value4` | float | MVRV Ratio |
| `weekList[].createTime` | string | Data timestamp (YYYY-MM-DD) |
| `weekList[].btcPrice` | float | Bitcoin price (nullable) |
| `weekList[].type` | string | Chart type identifier |

## Data Details

- **Frequency:** Weekly
- **Start Date:** ~2011 (based on data availability)
- **Last Updated:** 2026-01-27
- **Response Size:** ~765 KB

## Usage
```bash
curl -X GET "https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/mvrv-zscore/" \
  -H "Content-Type: application/json" \
  -o "data/coinank_mvrv_zscore.json"
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None |
| **Rate Limit** | Unknown |
| **Response Size** | 765 KB |
| **Status** | ✅ Working |
| **Data Points** | ~800+ weekly records |

## ⚠️ Limitations
- Weekly data only (not daily)
- Some value fields may be null
- Limited documentation available
- No explicit rate limits documented

## 💡 Use Cases
- Bitcoin market cycle analysis
- MVRV Z-Score historical analysis
- Market cycle top/bottom identification
- Long-term hodler behavior analysis
- Comparing current market cap to realized cap

## Interpretation Guide

| MVRV Z-Score Range | Market Condition |
|--------------------|-------------------|
| < 0 | Undervalued / Accumulation |
| 0-3 | Neutral / Healthy |
| 3-6 | Overvalued / Distribution |
| > 6 | Very overvalued / Bubble |

## Notes
- Primary value (value1) is the Z-Score
- Market Cap and Realized Cap provide context
- High Z-Score indicates potential market top
- Low Z-Score indicates potential market bottom
