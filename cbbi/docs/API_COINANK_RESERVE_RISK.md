# Coinank Reserve Risk API

## Endpoint
```
GET https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/reserve-risk/
```

## Request Body/Parameters
```json
None - GET request with required query parameter
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `type` | string | Chart type selector | Yes |

## Description
Coinank API endpoint for Reserve Risk data. Reserve Risk is an on-chain metric that measures the confidence of long-term Bitcoin holders relative to the price. It helps identify when risk-adjusted returns are attractive for long-term investors.

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
        "value1": 25253.998027382822,
        "value2": 41479.60971410741,
        "value3": 51822218.144033276,
        "value4": 0.0017213466191676476,
        "value5": null,
        "value6": null,
        "value7": null,
        "value8": null,
        "value9": null,
        "value10": null,
        "value11": null,
        "value12": null,
        "value13": null,
        "type": "/charts/reserve-risk/",
        "createTime": "2026-01-27",
        "btcPrice": 89204.0
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
| `weekList[].value1` | float | HODL Bank risk-adjusted return |
| `weekList[].value2` | float | Bitcoin price (USD) |
| `weekList[].value3` | float | HODL Bank value |
| `weekList[].value4` | float | Reserve Risk ratio |
| `weekList[].createTime` | string | Data timestamp (YYYY-MM-DD) |
| `weekList[].btcPrice` | float | Bitcoin price at time of data |
| `weekList[].type` | string | Chart type identifier |

## Data Details

- **Frequency:** Weekly
- **Start Date:** ~2011 (based on data availability)
- **Last Updated:** 2026-01-27
- **Response Size:** ~838 KB

## Usage
```bash
curl -X GET "https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/reserve-risk/" \
  -H "Content-Type: application/json" \
  -o "data/coinank_reserve_risk.json"
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None |
| **Rate Limit** | Unknown |
| **Response Size** | 838 KB |
| **Status** | ✅ Working |
| **Data Points** | ~800+ weekly records |

## ⚠️ Limitations
- Weekly data only (not daily)
- Some value fields may be null
- Limited documentation available
- No explicit rate limits documented

## 💡 Use Cases
- Long-term holder confidence analysis
- Risk-adjusted return assessment
- Identifying accumulation opportunities
- Market cycle timing
- Bitcoin supply dynamics

## Interpretation Guide

| Reserve Risk Range | Market Condition |
|--------------------|-------------------|
| < 0.002 | High opportunity / Accumulation |
| 0.002-0.01 | Neutral |
| 0.01-0.05 | Overvalued / Distribution |
| > 0.05 | Very overvalued / Top |

## Notes
- Lower values indicate better risk-adjusted opportunities
- High values indicate decreasing confidence in HODLing
- Best used for long-term investment decisions
- Combines price with on-chain holder behavior
