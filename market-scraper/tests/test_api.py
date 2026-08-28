"""Tests for the REST API endpoints."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from market_scraper.main import build_app


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(mock_db: AsyncMock):
    import market_scraper.db as db_mod
    from unittest.mock import Mock
    db_mod._db = mock_db
    # tracked_traders and trader_current_state collections need sync find()
    mock_db.tracked_traders = Mock()
    mock_db.trader_current_state = Mock()
    mock_db.trader_positions = Mock()
    mock_db.leaderboard_daily = Mock()
    app = build_app()
    with TestClient(app) as c:
        yield c
    db_mod._db = None


def _make_mock_cursor(return_value: list) -> AsyncMock:
    """Create a properly chained mock cursor.

    Motor's find() returns a cursor synchronously (not a coroutine),
    and sort()/limit() are also sync. Only to_list() is async.
    """
    from unittest.mock import Mock
    mock_cursor = Mock()
    mock_cursor.sort = Mock(return_value=mock_cursor)
    mock_cursor.limit = Mock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=return_value)
    return mock_cursor


class TestHealth:
    def test_health_ok(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.command = AsyncMock(return_value={"ok": 1})
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "mongo": "connected"}

    def test_health_fail(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.command = AsyncMock(side_effect=Exception("Connection refused"))
        response = client.get("/health")
        assert response.status_code == 503
        assert "unreachable" in response.json()["detail"]


async def _aiter_mock(items: list):
    for item in items:
        yield item


class TestTraders:
    def test_list_traders_empty(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.tracked_traders.find.return_value = _make_mock_cursor([])
        response = client.get("/api/v1/traders")
        assert response.status_code == 200
        assert response.json() == {"traders": [], "count": 0}

    def test_list_traders_with_positions(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.tracked_traders.find.return_value = _make_mock_cursor([{
            "eth": "0xabc",
            "name": "TestTrader",
            "score": 85.5,
            "acct_val": 500000,
            "tags": ["large", "consistent"],
            "roi_all_time": 1.2,
            "roi_month": 0.15,
        }])

        # Motor cursor is async-iterable — mock .find() to return async-iterable
        state_items = [{
            "eth": "0xabc",
            "positions": [{"position": {"szi": "1.5"}}],
            "open_orders": [],
            "margin_summary": {"accountValue": "100000"},
            "updated_at": datetime.now(UTC),
        }]

        async def _state_iter():
            for item in state_items:
                yield item

        mock_db.trader_current_state.find.return_value = _state_iter()

        response = client.get("/api/v1/traders")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["traders"][0]["eth"] == "0xabc"
        assert data["traders"][0]["position_status"] == "long"

    def test_get_trader_not_found(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.tracked_traders.find_one = AsyncMock(return_value=None)
        response = client.get("/api/v1/traders/0xnonexistent")
        assert response.status_code == 404

    def test_get_trader_found(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.tracked_traders.find_one = AsyncMock(
            return_value={
                "eth": "0xabc",
                "name": "TestTrader",
                "score": 85.5,
                "acct_val": 500000,
            }
        )
        mock_db.trader_current_state.find_one = AsyncMock(
            return_value={
                "positions": [{"position": {"szi": "1.5"}}],
                "updated_at": datetime.now(UTC),
            }
        )
        response = client.get("/api/v1/traders/0xabc")
        assert response.status_code == 200
        assert response.json()["eth"] == "0xabc"


class TestLeaderboard:
    def test_latest_leaderboard(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.leaderboard_daily.find_one = AsyncMock(
            return_value={
                "date": "2026-07-08",
                "total_fetched": 39000,
                "rows": [
                    {"eth": "0x1", "score": 90, "acct_val": 1000000},
                    {"eth": "0x2", "score": 85, "acct_val": 500000},
                    {"eth": "0x3", "score": 50, "acct_val": 20000},
                ],
            }
        )
        response = client.get("/api/v1/leaderboard?min_score=80&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["date"] == "2026-07-08"
        assert data["count"] == 2
        assert data["rows"][0]["score"] == 90

    def test_empty_leaderboard(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.leaderboard_daily.find_one = AsyncMock(return_value=None)
        response = client.get("/api/v1/leaderboard")
        assert response.status_code == 200
        assert response.json() == {"date": None, "rows": [], "count": 0}


class TestPositionHistory:
    def test_history(self, client: TestClient, mock_db: AsyncMock) -> None:
        mock_db.trader_positions.find.return_value = _make_mock_cursor([
            {"eth": "0xabc", "symbol": "BTC", "size": 1.5, "t": datetime.now(UTC)},
            {"eth": "0xabc", "symbol": "BTC", "size": 1.5, "t": datetime.now(UTC)},
        ])
        response = client.get("/api/v1/positions/0xabc/history?hours=24&limit=100")
        assert response.status_code == 200
        assert len(response.json()["positions"]) == 2