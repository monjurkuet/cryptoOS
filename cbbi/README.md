# CBBI API Repository

Complete CBBI (ColinTalksCrypto Bitcoin Bull Run Index) API documentation with download scripts for all endpoints.

## Repository Structure

```
cbbi/
├── README.md                          # Main documentation
├── scripts/
│   ├── download_all.sh                # Master download script
│   ├── download_cbbi.sh               # Download CBBI main data
│   ├── download_mvrv_zscore.sh        # Download MVRV Z-Score data
│   ├── download_reserve_risk.sh       # Download Reserve Risk data
│   ├── download_rhodl_ratio.sh        # Download RHODL Ratio data
│   └── download_coinmetrics.sh        # Download Coin Metrics data
├── docs/
│   ├── README.md                      # API documentation index
│   ├── API_CBBI_DATA.md               # CBBI main data API
│   ├── API_COINANK_MVRV.md            # Coinank MVRV Z-Score API
│   ├── API_COINANK_RESERVE_RISK.md    # Coinank Reserve Risk API
│   ├── API_COINANK_RHODL_RATIO.md     # Coinank RHODL Ratio API
│   └── API_COINMETRICS.md             # Coin Metrics API
├── data/
│   ├── cbbi/                          # CBBI data files
│   ├── coinank/                       # Coinank indicator data
│   └── coinmetrics/                   # Coin Metrics data
├── .gitignore
└── LICENSE
```

## Quick Start

### Download All Data

```bash
./scripts/download_all.sh
```

### Download Individual Datasets

```bash
# Download CBBI main data
./scripts/download_cbbi.sh

# Download Coinank indicator data
./scripts/download_mvrv_zscore.sh
./scripts/download_reserve_risk.sh
./scripts/download_rhodl_ratio.sh

# Download Coin Metrics data
./scripts/download_coinmetrics.sh
```

## API Overview

### 1. CBBI Main Data

**Endpoint:** `https://colintalkscrypto.com/cbbi/data/latest.json`

The primary CBBI data endpoint providing historical Bitcoin price and CBBI score data.

| Field | Type | Description |
|-------|------|-------------|
| `Price` | object | Bitcoin daily prices (Unix timestamp → price) |
| `PiCycle` | object | Pi Cycle Top Indicator values |
| `RUPL` | object | RUPL/NUPL Chart values |
| `RHODL` | object | RHODL Ratio values |
| `Puell` | object | Puell Multiple values |
| `2YMA` | object | 2-Year Moving Average values |
| `Trolololo` | object | Trolololo Trend Line values |
| `MVRV` | object | MVRV Z-Score values |
| `ReserveRisk` | object | Reserve Risk values |
| `Woobull` | object | Woobull Top Cap vs CVDD values |
| `Confidence` | object | Overall CBBI confidence score |

**Authentication:** None required
**Rate Limit:** Unknown
**Data Range:** 2011-06-27 to present

### 2. Coinank Indicator APIs

**Base URL:** `https://api.coinank.com/indicatorapi/chain/index/charts`

The CBBI uses multiple Coinank indicator APIs for various Bitcoin on-chain metrics.

| Metric | Endpoint Parameter | Status |
|--------|-------------------|--------|
| MVRV Z-Score | `type=/charts/mvrv-zscore/` | ✅ Working |
| Reserve Risk | `type=/charts/reserve-risk/` | ✅ Working |
| RHODL Ratio | `type=/charts/rhodl-ratio/` | ✅ Working |
| Puell Multiple | `type=/charts/puell-multiple/` | ❌ 500 Error |
| 2-Year MA | `type=/charts/2y-ma/` | ❌ 500 Error |
| Pi Cycle Top | `type=/charts/pi-cycle-top/` | ❌ 500 Error |
| NUPL/RUPL | `type=/charts/nupl/` | ❌ 500 Error |

**Authentication:** None required
**Rate Limit:** Unknown
**Data Frequency:** Weekly

### 3. Coin Metrics API

**Endpoint:** `https://community-api.coinmetrics.io/v4/timeseries/asset-metrics`

Free community API for Bitcoin blockchain and market data.

| Parameter | Description | Example |
|-----------|-------------|---------|
| `assets` | Asset identifier | `btc` |
| `metrics` | Metrics to retrieve | `PriceUSD,BlkCnt` |
| `frequency` | Data frequency | `1d`, `1h`, `1w` |
| `start_time` | Start date | `2025-01-01` |
| `page_size` | Results per page | `100` (max) |
| `paging_from` | Pagination direction | `start`, `end` |

**Authentication:** None required (Community API)
**Rate Limit:** Unknown
**Data Range:** 2009-01-03 to present

## Data Sources

The CBBI uses a multi-source approach:

1. **Primary:** Coinank API for most on-chain metrics
2. **Secondary:** Coin Metrics Community API for blockchain data
3. **Internal:** CBBI's own aggregated dataset

## Metrics Description

### Pi Cycle Top Indicator
Identifies market cycle tops by comparing 111-day and 350-day moving averages.

### RUPL/NUPL Chart
Realized Price vs Unrealized Profit/Loss ratio.

### RHODL Ratio
Ratio of RHODL (Realized HODL) bands to assess market cycles.

### Puell Multiple
Measures miner profitability by dividing current supply by 365-day moving average.

### 2-Year Moving Average
Compares current price to 2-year rolling average.

### MVRV Z-Score
Market Value to Realized Value Z-Score for identifying market cycles.

### Reserve Risk
Measures confidence of long-term holders vs Bitcoin price.

### Trolololo Trend Line
Logarithmic growth curve for Bitcoin price.

### Woobull Top Cap vs CVDD
Compares top cap to Cost Basis Value Density.

### Confidence Score
Overall CBBI confidence score indicating market cycle position.

## Requirements

- `curl` - For downloading data
- `bash` - For running scripts
- `python3` - For data analysis (optional)

## Features

- ✅ No authentication required for most endpoints
- ✅ 5+ download scripts
- ✅ 5+ detailed API documentation files
- ✅ GitHub-ready structure
- ✅ Comprehensive data coverage
- ✅ Historical data from 2011

## License

MIT License
