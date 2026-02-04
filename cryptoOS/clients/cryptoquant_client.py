class CryptoQuantClient:
    def __init__(self, api_key: str = None):
        from ..config import Settings

        self.settings = Settings()
        self.api_key = api_key or self.settings.cryptoquant_api_key
        self.base_url = self.settings.cryptoquant_api_url

    def get_mvrv_ratio(self):
        pass

    def get_funding_rates(self):
        pass

    def get_exchange_reserves(self):
        pass

    def get_exchange_netflow(self):
        pass
