import pytest
from cryptoOS.clients import CBBIClient, HyperliquidClient


class TestCBBIClient:
    def test_client_initialization(self):
        client = CBBIClient()
        assert client is not None


class TestHyperliquidClient:
    def test_client_initialization(self):
        client = HyperliquidClient()
        assert client is not None

    def test_get_ticker(self):
        client = HyperliquidClient()
        result = client.get_ticker("BTC")
        assert result is not None
