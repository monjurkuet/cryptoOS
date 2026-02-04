class HyperliquidCollector:
    def __init__(self):
        from ..clients import HyperliquidClient

        self.client = HyperliquidClient()

    def download_tickers(self):
        coins = ["BTC", "ETH", "SOL"]
        return {coin: self.client.get_ticker(coin) for coin in coins}

    def download_orderbooks(self, coin: str):
        return self.client.get_orderbook(coin)

    def download_candles(self, coin: str, interval: str = "1h"):
        return self.client.get_candles(coin, interval)
