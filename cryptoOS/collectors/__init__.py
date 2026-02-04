class CBBICollector:
    def __init__(self):
        from ..clients import CBBIClient

        self.client = CBBIClient()

    def download_all(self):
        return self.client.get_latest()

    def get_latest(self):
        return self.client.get_latest()

    def get_mvrv_zscore(self):
        pass

    def get_reserve_risk(self):
        pass

    def get_rhodl_ratio(self):
        pass
