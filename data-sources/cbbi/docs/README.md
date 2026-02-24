# CBBI API Documentation Index

## Available APIs

### 1. CBBI Main Data API
- **Documentation:** [API_CBBI_DATA.md](API_CBBI_DATA.md)
- **Endpoint:** `https://colintalkscrypto.com/cbbi/data/latest.json`
- **Description:** Primary CBBI data with all 11 metrics

### 2. Coinank Indicator APIs

#### MVRV Z-Score
- **Documentation:** [API_COINANK_MVRV.md](API_COINANK_MVRV.md)
- **Endpoint:** `https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/mvrv-zscore/`
- **Status:** ✅ Working

#### Reserve Risk
- **Documentation:** [API_COINANK_RESERVE_RISK.md](API_COINANK_RESERVE_RISK.md)
- **Endpoint:** `https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/reserve-risk/`
- **Status:** ✅ Working

#### RHODL Ratio
- **Documentation:** [API_COINANK_RHODL_RATIO.md](API_COINANK_RHODL_RATIO.md)
- **Endpoint:** `https://api.coinank.com/indicatorapi/chain/index/charts?type=/charts/rhodl-ratio/`
- **Status:** ✅ Working

### 3. Coin Metrics API
- **Documentation:** [API_COINMETRICS.md](API_COINMETRICS.md)
- **Endpoint:** `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics`
- **Description:** Bitcoin blockchain and market data

## Quick Links

- [Main README](../README.md)
- [Download Scripts](../scripts/)
- [Data Directory](../data/)

## API Summary

| API | Authentication | Rate Limit | Status |
|-----|----------------|------------|--------|
| CBBI Data | None | Unknown | ✅ Working |
| Coinank MVRV | None | Unknown | ✅ Working |
| Coinank Reserve Risk | None | Unknown | ✅ Working |
| Coinank RHODL | None | Unknown | ✅ Working |
| Coin Metrics | None | Unknown | ✅ Working |

## Data Coverage

| Metric | Start Date | Frequency |
|--------|-----------|----------|
| Bitcoin Price | 2011-06-27 | Daily |
| Pi Cycle Top | 2011-06-27 | Daily |
| RUPL/NUPL | 2011-06-27 | Daily |
| RHODL Ratio | 2011-06-27 | Daily |
| Puell Multiple | 2011-06-27 | Daily |
| 2-Year MA | 2011-06-27 | Daily |
| MVRV Z-Score | 2011-06-27 | Daily |
| Reserve Risk | 2011-06-27 | Daily |
| CBBI Confidence | 2011-06-27 | Daily |
