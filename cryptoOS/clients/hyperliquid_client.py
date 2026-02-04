class HyperliquidClient:
    def __init__(self, address: str = None):
        from ..config import Settings

        self.settings = Settings()
        self.base_url = self.settings.hyperliquid_api_url
        self.address = address

    def get_ticker(self, coin: str):
        import httpx

        payload = {"type": "ticker", "coin": coin}
        with httpx.Client() as client:
            response = client.post(self.base_url, json=payload)
            return response.json()

    def get_orderbook(self, coin: str):
        pass

    def get_candles(self, coin: str, interval: str = "1h"):
        pass

    def get_positions(self):
        pass
