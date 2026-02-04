class CBBIClient:
    def __init__(self):
        from ..config import Settings

        self.settings = Settings()
        self.base_url = self.settings.cbbi_base_url

    def get_latest(self):
        import requests

        response = requests.get(f"{self.base_url}/latest.json")
        return response.json()

    def get_mvrv_zscore(self):
        pass

    def get_reserve_risk(self):
        pass

    def get_rhodl_ratio(self):
        pass
