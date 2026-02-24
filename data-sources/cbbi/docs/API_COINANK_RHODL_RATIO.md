# Coinank RHODL Ratio API

## Endpoint
```
GET https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/rhodl-ratio/
```

## Request Body/Parameters
```json
None - GET request with required query parameter
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `type` | string | Chart type selector | Yes |

## Description
Coinank API endpoint for RHODL Ratio (Realized HODL Ratio) data. RHODL Ratio compares the Realized HODL bands to assess where current Bitcoin supply is concentrated and identify market cycles.

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
        "value1": 2027.290326016355,
        "value2": null,
        "value3": null,
        "value4": null,
        "value5": null,
        "value6": null,
        "value7": null,
        "value8": null,
        "value9": null,
        "value10": null,
        "value11": null,
        "value12": null,
        "value13": null,
        "type": "/charts/rhodl-ratio/",
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
| `weekList[].value1` | float | RHODL Ratio primary value |
| `weekList[].value2-13` | float | Additional values (mostly null) |
| `weekList[].createTime` | string | Data timestamp (YYYY-MM-DD) |
| `weekList[].btcPrice` | float | Bitcoin price at time of data |
| `weekList[].type` | string | Chart type identifier |

## Data Details

- **Frequency:** Weekly
- **Start Date:** ~2011 (based on data availability)
- **Last Updated:** 2026-01-27
- **Response Size:** ~599 KB

## Usage
```bash
curl -X GET "https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/rhodl-ratio/" \
  -H "Content-Type: application/json" \
  -o "data/coinank_rhodl_ratio.json"
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None |
| **Rate Limit** | Unknown |
| **Response Size** | 599 KB |
| **Status** | ✅ Working |
| **Data Points** | ~800+ weekly records |

## ⚠️ Limitations
- Weekly data only (not daily)
- Only primary value (value1) is populated
- Limited documentation available
- No explicit rate limits documented

## 💡 Use Cases
- Identifying Bitcoin supply dynamics
- HODL wave analysis
- Market cycle detection
- Long-term holder behavior
- Supply concentration analysis

## Interpretation Guide

| RHODL Ratio Range | Market Condition |
|--------------------|-------------------|
| < 100 | Accumulation phase |
| 100-500 | Early bull market |
| 500-2000 | Mid bull market |
| 2000-5000 | Late bull market / Top |
| > 5000 | Potential cycle top |

## Notes
- Higher values indicate older coins moving (distribution)
- Lower values indicate accumulation by long-term holders
- Works best in combination with other metrics
- Logarithmic scale is typically used for visualization
