# cryptoOS - Cryptocurrency Data Aggregation Platform

<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Contributors](https://img.shields.io/badge/Contributors-Welcome-orange.svg)

**Comprehensive cryptocurrency on-chain data aggregation and analysis platform**

[cryptosharen.com](https://cryptosharen.com) · [Report Bug](https://github.com/monjurkuet/cryptoOS/issues) · [Request Feature](https://github.com/monjurkuet/cryptoOS/issues)

</div>

---

## 🚀 Features

### 📊 Multi-Source Data Aggregation

| Module | Description | Status |
|--------|-------------|--------|
| **CBBI** | ColinTalksCrypto Bitcoin Bull Run Index | ✅ Complete |
| **Hyperliquid** | Decentralized exchange trading data | ✅ Complete |
| **CryptoQuant** | On-chain metrics and indicators | ✅ Complete |
| **Bitcoin Magazine Pro** | Market indicators and fear/greed index | ✅ Complete |

### 🛠️ Supported Data Types

- **Price Data**: Historical BTC prices and market data
- **On-Chain Metrics**: MVRV Z-Score, Reserve Risk, RHODL Ratio
- **Exchange Flows**: Netflows, reserves, whale activity
- **Derivatives**: Open interest, funding rates, liquidations
- **DeFi Data**: Vaults, liquidity, trading activity

---

## 📁 Project Structure

```
cryptoOS/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── setup.py                     # Package setup
├── Makefile                     # Development commands
├── cryptoOS/                    # Main package
│   ├── __init__.py
│   ├── config.py               # Configuration
│   ├── clients/                # API clients
│   │   ├── cbbi_client.py
│   │   ├── hyperliquid_client.py
│   │   └── cryptoquant_client.py
│   ├── collectors/             # Data collectors
│   │   ├── cbbi_collector.py
│   │   ├── hyperliquid_collector.py
│   │   └── cryptoquant_collector.py
│   ├── processors/            # Data processors
│   │   ├── transformer.py
│   │   └── analyzer.py
│   ├── storage/               # Storage backends
│   │   ├── json_storage.py
│   │   └── database.py
│   └── utils/                 # Utilities
│       ├── logger.py
│       └── helpers.py
├── scripts/                    # Utility scripts
│   ├── download_all.sh
│   └── migrate_data.sh
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_clients.py
│   └── test_collectors.py
├── notebooks/                  # Jupyter notebooks
│   └── analysis_examples.ipynb
├── docs/                       # Documentation
│   ├── API.md
│   ├── Architecture.md
│   └── Contributing.md
├── data/                       # Data storage (gitignored)
│   ├── raw/
│   ├── processed/
│   └── backup/
└── .github/                    # GitHub configuration
    ├── workflows/
    │   ├── ci.yml
    │   └── data_pipeline.yml
    └── ISSUE_TEMPLATE.md
```

---

## 🏃 Quick Start

### Prerequisites

- Python 3.10 or higher
- pip or poetry
- Git

### Installation

```bash
# Clone the repository
git clone git@github.com:monjurkuet/cryptoOS.git
cd cryptoOS

# Install dependencies
pip install -r requirements.txt

# Or with poetry
poetry install

# Verify installation
python -c "import cryptoOS; print(cryptoOS.__version__)"
```

### Basic Usage

```python
from cryptoOS.clients import HyperliquidClient
from cryptoOS.collectors import CBBICollector

# Initialize clients
client = HyperliquidClient()
collector = CBBICollector()

# Fetch data
data = client.get_ticker("BTC")
cbbi_data = collector.get_latest()

print(f"BTC Ticker: {data}")
print(f"CBBI Latest: {cbbi_data}")
```

---

## 📖 Modules

### CBBI Module

Bitcoin Bull Run Index aggregation with multiple on-chain indicators.

```python
from cryptoOS.collectors import CBBICollector

collector = CBBICollector()

# Get all CBBI data
data = collector.download_all()

# Get specific indicator
mvrv = collector.get_mvrv_zscore()
reserve_risk = collector.get_reserve_risk()
rhodl = collector.get_rhodl_ratio()
```

**Documentation**: [CBBI Docs](cbbi/README.md)

### Hyperliquid Module

Decentralized exchange data including trading, vaults, and user activity.

```python
from cryptoOS.clients import HyperliquidClient

client = HyperliquidClient(address="0x...")

# Market data
ticker = client.get_ticker("BTC")
orderbook = client.get_orderbook("BTC")
candles = client.get_candles("BTC", "1h")

# User data
positions = client.get_positions()
orders = client.get_open_orders()
```

**Documentation**: [Hyperliquid Docs](hyperliquid/README.md)

### CryptoQuant Module

Professional on-chain analytics and market indicators.

```python
from cryptoOS.clients import CryptoQuantClient

client = CryptoQuantClient(api_key="your_key")

# Market indicators
mvrv = client.get_mvrv_ratio()
funding = client.get_funding_rates()

# Exchange flows
reserves = client.get_exchange_reserves()
netflow = client.get_exchange_netflow()
```

**Documentation**: [CryptoQuant Docs](cryptoquant/README.md)

---

## 🔧 Configuration

Create a `.env` file in the root directory:

```env
# API Keys (optional)
CRYPTOQUANT_API_KEY=your_api_key
HYPERLIQUID_PRIVATE_KEY=your_private_key

# Settings
DATA_DIR=./data
LOG_LEVEL=INFO
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

---

## 📊 Data Sources

| Source | Type | Free | API Key Required |
|--------|------|------|------------------|
| CBBI | On-Chain | ✅ | No |
| Hyperliquid | DEX | ✅ | No |
| CoinMetrics | Blockchain | ✅ (Community) | No |
| CryptoQuant | On-Chain | ❌ | Yes |
| Bitcoin Magazine Pro | Market | ✅ | No |

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=cryptoOS

# Run specific test
pytest tests/test_clients.py -v
```

---

## 📦 CI/CD Pipeline

Automated workflows for:

- 🟢 **CI**: Code quality, tests, type checking
- 🔵 **Data Pipeline**: Daily data collection and backup
- 🟣 **Release**: Version management and releases

---

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](docs/Contributing.md) for details.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [ColinTalksCrypto](https://colintalkscrypto.com) for CBBI
- [Hyperliquid](https://hyperliquid.xyz) for DEX data
- [CryptoQuant](https://cryptoquant.com) for on-chain analytics
- [CoinMetrics](https://coinmetrics.io) for blockchain data

---

<div align="center">

**Made with ❤️ for the crypto community**

[cryptosharen.com](https://cryptosharen.com)

</div>
