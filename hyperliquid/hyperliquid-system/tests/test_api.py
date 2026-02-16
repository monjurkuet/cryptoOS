"""
Tests for API clients.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.hyperliquid import HyperliquidClient
from src.api.cloudfront import CloudFrontClient
from src.api.stats_data import StatsDataClient


class TestHyperliquidClient:
    """Tests for HyperliquidClient."""

    @pytest.mark.asyncio
    async def test_get_candles(self):
        """Test getting candles."""
        client = HyperliquidClient()

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = [
                {
                    "t": 1704067200000,
                    "o": "75000",
                    "h": "75100",
                    "l": "74900",
                    "c": "75050",
                    "v": "150",
                }
            ]

            async with client:
                result = await client.get_candles("BTC", "1h", 1704067200000)

            assert len(result) == 1
            assert result[0]["o"] == "75000"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_ticker(self):
        """Test getting ticker."""
        client = HyperliquidClient()

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "coin": "BTC",
                "px": "75000",
                "volume": "10000000",
            }

            async with client:
                result = await client.get_ticker("BTC")

            assert result["coin"] == "BTC"
            assert result["px"] == "75000"

    @pytest.mark.asyncio
    async def test_get_clearinghouse_state(self):
        """Test getting clearinghouse state."""
        client = HyperliquidClient()

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "marginSummary": {"accountValue": "1000000"},
                "assetPositions": [],
            }

            async with client:
                result = await client.get_clearinghouse_state("0x123...")

            assert "marginSummary" in result


class TestCloudFrontClient:
    """Tests for CloudFrontClient."""

    @pytest.mark.asyncio
    async def test_get_open_interest(self):
        """Test getting open interest."""
        client = CloudFrontClient()

        with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "chart_data": [
                    {"time": "2024-01-01T00:00:00", "coin": "BTC", "open_interest": 1000000}
                ]
            }

            async with client:
                result = await client.get_open_interest()

            assert "chart_data" in result

    def test_filter_btc(self):
        """Test BTC filtering."""
        data = {
            "chart_data": [
                {"time": "2024-01-01T00:00:00", "coin": "BTC", "open_interest": 1000000},
                {"time": "2024-01-01T00:00:00", "coin": "ETH", "open_interest": 500000},
            ]
        }

        result = CloudFrontClient.filter_btc(data)

        assert len(result) == 1
        assert result[0]["coin"] == "BTC"


class TestStatsDataClient:
    """Tests for StatsDataClient."""

    @pytest.mark.asyncio
    async def test_get_leaderboard(self):
        """Test getting leaderboard."""
        client = StatsDataClient()

        with patch.object(client, "_fetch", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "leaderboardRows": [{"ethAddress": "0x123...", "accountValue": "1000000"}]
            }

            async with client:
                result = await client.get_leaderboard()

            assert "leaderboardRows" in result
            assert len(result["leaderboardRows"]) == 1

    def test_extract_trader_info(self):
        """Test extracting trader info."""
        trader_data = {
            "ethAddress": "0x123...",
            "accountValue": "1000000",
            "displayName": "TestTrader",
            "windowPerformances": [["day", {"pnl": "1000", "roi": "0.01", "vlm": "100000"}]],
        }

        result = StatsDataClient.extract_trader_info(trader_data)

        assert result["ethAddress"] == "0x123..."
        assert result["accountValue"] == 1000000
        assert "day" in result["performances"]
