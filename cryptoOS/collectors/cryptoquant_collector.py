class CryptoQuantCollector:
    def __init__(self):
        from ..clients import CryptoQuantClient

        self.client = CryptoQuantClient()

    def download_indicators(self):
        return {
            "mvrv_ratio": self.client.get_mvrv_ratio(),
            "funding_rates": self.client.get_funding_rates(),
            "exchange_reserves": self.client.get_exchange_reserves(),
            "exchange_netflow": self.client.get_exchange_netflow(),
        }

    def get_mvrv_ratio(self):
        pass

    def get_funding_rates(self):
        pass
