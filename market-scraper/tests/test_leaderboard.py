"""Tests for leaderboard scoring and filtering logic."""
from unittest.mock import MagicMock, patch

import pytest

from market_scraper.models import LeaderboardRow
from market_scraper.services.leaderboard import LeaderboardService


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.leaderboard.weights = {
        "roi_all_time": 30,
        "roi_month": 25,
        "roi_week": 20,
        "account_value": 15,
        "volume_month": 10,
    }
    s.leaderboard.min_account_value = 10000.0
    s.leaderboard.max_tracked = 1000
    return s


@pytest.fixture
def service(settings: MagicMock) -> LeaderboardService:
    with patch("market_scraper.services.leaderboard.get_settings", return_value=settings):
        svc = LeaderboardService()
        return svc


class TestScoring:
    def test_high_roi_all_time_scores_well(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xabc123",
            "displayName": "TestTrader",
            "accountValue": "500000",
            "windowPerformances": [
                ["allTime", {"roi": "2.5", "vlm": "50000000", "pnl": "1250000"}],
                ["year", {"roi": "0.8", "vlm": "30000000", "pnl": "400000"}],
                ["month", {"roi": "0.15", "vlm": "5000000", "pnl": "75000"}],
                ["week", {"roi": "0.05", "vlm": "1000000", "pnl": "25000"}],
                ["day", {"roi": "0.01", "vlm": "100000", "pnl": "5000"}],
            ],
        }
        result = service._score_trader(row, 0)
        assert result.eth == "0xabc123"
        assert result.name == "TestTrader"
        assert result.acct_val == 500000
        assert result.roi_all_time == 2.5
        assert result.roi_year == 0.8
        assert result.roi_month == 0.15
        assert result.roi_week == 0.05
        assert result.roi_day == 0.01
        assert result.volume_month == 5000000
        assert result.pnl_all_time == 1250000
        assert result.score > 50  # Should score well
        assert result.rank == 1
        assert "mid" in result.tags  # 500K < 1M -> mid, not large
        assert "high_performer" in result.tags  # allTime ROI > 1.0

    def test_whale_tag_applied(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xwhale",
            "accountValue": "15000000",
            "windowPerformances": [],
        }
        result = service._score_trader(row, 0)
        assert "whale" in result.tags

    def test_elite_tag_applied(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xelite",
            "accountValue": "50000000",
            "windowPerformances": [
                ["allTime", {"roi": "5.0", "vlm": "500000000"}],
                ["year", {"roi": "2.0"}],
                ["month", {"roi": "0.35", "vlm": "300000000"}],
                ["week", {"roi": "0.1"}],
                ["day", {"roi": "0.05"}],
            ],
        }
        result = service._score_trader(row, 0)
        # Score: 30 (allTime) + 15 (month: min(0.35*50,25)=17.5->17.5) +
        #         10 (week) + 15 (acct_val) + 10 (volume: 300M>=100M) = 82.5 > 80
        assert "whale" in result.tags
        assert "consistent" in result.tags
        assert "high_performer" in result.tags
        assert "elite" in result.tags

    def test_negative_week_roi_reduces_score(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xneg",
            "accountValue": "100000",
            "windowPerformances": [
                ["allTime", {"roi": "0.5", "vlm": "10000000"}],
                ["year", {"roi": "0.1"}],
                ["month", {"roi": "0.1"}],
                ["week", {"roi": "-0.05"}],
                ["day", {"roi": "0.02"}],
            ],
        }
        result = service._score_trader(row, 0)
        assert result.score > 0  # Still positive due to allTime and month

    def test_consistent_tag_when_all_positive(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xconsistent",
            "accountValue": "50000",
            "windowPerformances": [
                ["allTime", {"roi": "0.1"}],
                ["year", {"roi": "0.05"}],
                ["month", {"roi": "0.01"}],
                ["week", {"roi": "0.005"}],
                ["day", {"roi": "0.001"}],
            ],
        }
        result = service._score_trader(row, 0)
        assert "consistent" in result.tags

    def test_consistent_tag_missing_when_one_negative(self, service: LeaderboardService) -> None:
        row = {
            "ethAddress": "0xinconsistent",
            "accountValue": "50000",
            "windowPerformances": [
                ["allTime", {"roi": "0.1"}],
                ["year", {"roi": "0.05"}],
                ["month", {"roi": "0.01"}],
                ["week", {"roi": "-0.005"}],
                ["day", {"roi": "0.001"}],
            ],
        }
        result = service._score_trader(row, 0)
        assert "consistent" not in result.tags


class TestFiltering:
    def test_filter_requires_positive_all_time(self, service: LeaderboardService) -> None:
        rows = [
            {"ethAddress": "0x1", "accountValue": "100000",
             "windowPerformances": [["allTime", {"roi": "0.5"}], ["year", {"roi": "0.1"}], ["month", {"roi": "0.05"}]]},
            {"ethAddress": "0x2", "accountValue": "100000",
             "windowPerformances": [["allTime", {"roi": "-0.1"}], ["year", {"roi": "0.1"}], ["month", {"roi": "0.05"}]]},
        ]
        scored = [service._score_trader(r, i) for i, r in enumerate(rows)]
        filtered = [r for r in scored if r.roi_all_time > 0 and r.roi_year > 0 and r.roi_month > 0]
        assert len(filtered) == 1
        assert filtered[0].eth == "0x1"

    def test_filter_requires_min_account_value(self, service: LeaderboardService) -> None:
        rows = [
            {"ethAddress": "0x1", "accountValue": "100000",
             "windowPerformances": [["allTime", {"roi": "0.5"}], ["year", {"roi": "0.1"}], ["month", {"roi": "0.05"}]]},
            {"ethAddress": "0x2", "accountValue": "5000",
             "windowPerformances": [["allTime", {"roi": "0.5"}], ["year", {"roi": "0.1"}], ["month", {"roi": "0.05"}]]},
        ]
        scored = [service._score_trader(r, i) for i, r in enumerate(rows)]
        filtered = [
            r for r in scored
            if r.roi_all_time > 0 and r.roi_year > 0 and r.roi_month > 0
            and r.acct_val >= 10000
        ]
        assert len(filtered) == 1
        assert filtered[0].eth == "0x1"


class TestSortOrder:
    def test_top_traders_highest_score(self, service: LeaderboardService) -> None:
        rows = [
            {"ethAddress": "0xlow", "accountValue": "100000",
             "windowPerformances": [["allTime", {"roi": "0.1"}], ["year", {"roi": "0.01"}], ["month", {"roi": "0.005"}]]},
            {"ethAddress": "0xhigh", "accountValue": "15000000",
             "windowPerformances": [
                 ["allTime", {"roi": "5.0", "vlm": "500000000"}],
                 ["year", {"roi": "2.0"}],
                 ["month", {"roi": "0.3"}],
                 ["week", {"roi": "0.1"}],
                 ["day", {"roi": "0.05"}],
             ]},
            {"ethAddress": "0xmid", "accountValue": "500000",
             "windowPerformances": [
                 ["allTime", {"roi": "1.0", "vlm": "50000000"}],
                 ["year", {"roi": "0.3"}],
                 ["month", {"roi": "0.1"}],
                 ["week", {"roi": "0.05"}],
                 ["day", {"roi": "0.01"}],
             ]},
        ]
        scored = [service._score_trader(r, i) for i, r in enumerate(rows)]
        # All pass filter
        filtered = [r for r in scored if r.roi_all_time > 0 and r.roi_year > 0 and r.roi_month > 0]
        filtered.sort(key=lambda x: x.score, reverse=True)
        assert filtered[0].eth == "0xhigh"
        assert filtered[1].eth == "0xmid"
        assert filtered[2].eth == "0xlow"

    def test_max_tracked_limit(self, service: LeaderboardService) -> None:
        service.settings.leaderboard.max_tracked = 2
        rows = [
            {"ethAddress": f"0x{i:040x}", "accountValue": "100000",
             "windowPerformances": [["allTime", {"roi": str(0.1 * i)}], ["year", {"roi": "0.1"}], ["month", {"roi": "0.05"}]]}
            for i in range(1, 6)
        ]
        scored = [service._score_trader(r, i) for i, r in enumerate(rows)]
        filtered = [r for r in scored if r.roi_all_time > 0 and r.roi_year > 0 and r.roi_month > 0]
        filtered.sort(key=lambda x: x.score, reverse=True)
        tracked = filtered[: service.settings.leaderboard.max_tracked]
        assert len(tracked) == 2
        # Top 2 should have highest scores
        assert tracked[0].score >= tracked[1].score
