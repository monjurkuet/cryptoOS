# CBBI Main Data API

## Endpoint
```
GET https://colintalkscrypto.com/cbbi/data/latest.json
```

## Request Body/Parameters
```json
None - GET request with no parameters
```

## Description
Primary CBBI data endpoint providing comprehensive historical Bitcoin price and CBBI score data. This is the main data source for the CBBI index, containing 11 key metrics for analyzing Bitcoin market cycles.

## Response Format
```json
{
  "Price": {
    "1309132800": 16.7523,
    "1309219200": 16.9618,
    ...
  },
  "PiCycle": {
    "1309132800": 0.1,
    "1309219200": 0.11,
    ...
  },
  "RUPL": {
    "1309132800": 0.5,
    "1309219200": 0.52,
    ...
  },
  "RHODL": {
    "1309132800": 0.3,
    "1309219200": 0.31,
    ...
  },
  "Puell": {
    "1309132800": 0.8,
    "1309219200": 0.81,
    ...
  },
  "2YMA": {
    "1309132800": 10.0,
    "1309219200": 10.1,
    ...
  },
  "Trolololo": {
    "1309132800": 10000.0,
    "1309219200": 10050.0,
    ...
  },
  "MVRV": {
    "1309132800": 0.5,
    "1309219200": 0.51,
    ...
  },
  "ReserveRisk": {
    "1309132800": 0.001,
    "1309219200": 0.0011,
    ...
  },
  "Woobull": {
    "1309132800": 0.4,
    "1309219200": 0.41,
    ...
  },
  "Confidence": {
    "1309132800": 10,
    "1309219200": 11,
    ...
  }
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `Price` | object | Bitcoin daily closing prices (Unix timestamp → USD) |
| `PiCycle` | object | Pi Cycle Top Indicator values (0-1 scale) |
| `RUPL` | object | RUPL/NUPL Chart values (ratio) |
| `RHODL` | object | RHODL Ratio values (log scale) |
| `Puell` | object | Puell Multiple values (ratio) |
| `2YMA` | object | 2-Year Moving Average values (USD) |
| `Trolololo` | object | Trolololo Trend Line values (log scale) |
| `MVRV` | object | MVRV Z-Score values (z-score) |
| `ReserveRisk` | object | Reserve Risk values (log scale) |
| `Woobull` | object | Woobull Top Cap vs CVDD values (ratio) |
| `Confidence` | object | Overall CBBI confidence score (0-100) |

## Data Range

- **Start Date:** 2011-06-27 (Unix timestamp: 1309132800)
- **End Date:** Present
- **Frequency:** Daily
- **Total Entries:** 5,335+ per metric

## Usage
```bash
curl -X GET "https://colintalkscrypto.com/cbbi/data/latest.json" -o "data/latest.json"
```

## ✅ Test Results

| Metric | Value |
|--------|-------|
| **Authentication** | None |
| **Rate Limit** | Unknown |
| **Response Size** | 1.4 MB |
| **Status** | ✅ Working |
| **Data Points** | 5,335+ per metric |

## ⚠️ Limitations
- No authentication or rate limit documentation available
- Data is updated daily (may have 1-day lag)
- All values are stored as Unix timestamps (seconds) as keys

## 💡 Use Cases
- Historical Bitcoin price analysis
- CBBI confidence score tracking
- On-chain metric analysis
- Market cycle identification
- Backtesting trading strategies

## Notes
- Primary data source for the CBBI website
- All 11 metrics share the same timestamp keys for easy correlation
- Confidence score is the main output of the CBBI algorithm
- Timestamp format: Unix epoch (seconds since 1970-01-01)
