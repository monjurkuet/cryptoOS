# tests/unit/api/routes/test_traders.py

"""Tests for trader API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from market_scraper.api.routes.traders import router


@pytest.fixture
def mock_lifecycle():
    """Create a mock lifecycle manager."""
    lifecycle = MagicMock()
    lifecycle._settings = MagicMock()
    lifecycle._settings.hyperliquid = MagicMock()
    lifecycle._settings.hyperliquid.symbol = "BTC"
    return lifecycle


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock()
    repo.get_trader_current_states = AsyncMock(return_value={})
    return repo


@pytest.fixture
def app(mock_lifecycle, mock_repository):
    """Create a test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/traders")

    # Override the get_lifecycle dependency
    mock_lifecycle.repository = mock_repository
    app.state.lifecycle = mock_lifecycle

    return app


class TestListTraders:
    """Tests for list_traders endpoint."""

    @pytest.mark.asyncio
    async def test_list_traders_success(self, app, mock_repository) -> None:
        """Test successful list traders response."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0x1234567890123456789012345678901234567890",
                "name": "Test Trader",
                "score": 75.5,
                "tags": ["whale"],
                "acct_val": 5000000,
                "active": True,
            }
        ]
        mock_repository.count_tracked_traders.return_value = 1

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["traders"]) == 1
        assert data["traders"][0]["address"] == "0x1234567890123456789012345678901234567890"
        assert data["traders"][0]["score"] == 75.5
        assert data["traders"][0]["has_open_orders"] is False
        assert data["traders"][0]["open_order_count"] == 0
        mock_repository.get_trader_current_states.assert_called_once_with(
            addresses=["0x1234567890123456789012345678901234567890"],
            symbol="BTC",
        )
        mock_repository.get_trader_current_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_traders_with_filters(self, app, mock_repository) -> None:
        """Test list traders with min_score and tag filters."""
        mock_repository.get_tracked_traders.return_value = []
        mock_repository.count_tracked_traders.return_value = 0

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders", params={"min_score": 50, "tag": "whale"})

        assert response.status_code == 200
        mock_repository.get_tracked_traders.assert_called_once_with(
            min_score=50.0,
            tag="whale",
            active_only=True,
            limit=50,
        )
        mock_repository.get_trader_current_states.assert_called_once_with(
            addresses=[],
            symbol="BTC",
        )
        mock_repository.get_trader_current_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_traders_filtered_total_matches_filtered_rows(
        self, app, mock_repository
    ) -> None:
        """Filtered queries should report total equal to filtered returned rows."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0x1111111111111111111111111111111111111111",
                "name": "Trader A",
                "score": 80,
                "tags": [],
                "acct_val": 100000,
                "active": True,
            },
            {
                "eth": "0x2222222222222222222222222222222222222222",
                "name": "Trader B",
                "score": 79,
                "tags": [],
                "acct_val": 90000,
                "active": True,
            },
        ]
        mock_repository.count_tracked_traders.return_value = 999
        mock_repository.get_trader_current_states.return_value = {
            "0x1111111111111111111111111111111111111111": {
                "positions": [{"position": {"coin": "BTC", "szi": 1.0}}],
                "updated_at": datetime.now(UTC),
            },
            "0x2222222222222222222222222222222222222222": {
                "positions": [],
                "updated_at": datetime.now(UTC),
            },
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders", params={"has_positions": True})

        assert response.status_code == 200
        data = response.json()
        assert len(data["traders"]) == 1
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_traders_filters_by_has_open_orders(self, app, mock_repository) -> None:
        """Open-order filter should return only matching traders."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0x1111111111111111111111111111111111111111",
                "name": "Trader A",
                "score": 80,
                "tags": [],
                "acct_val": 100000,
                "active": True,
            },
            {
                "eth": "0x2222222222222222222222222222222222222222",
                "name": "Trader B",
                "score": 70,
                "tags": [],
                "acct_val": 90000,
                "active": True,
            },
        ]
        mock_repository.count_tracked_traders.return_value = 2
        mock_repository.get_trader_current_states.return_value = {
            "0x1111111111111111111111111111111111111111": {
                "positions": [],
                "open_orders": [{"coin": "BTC", "sz": "1", "oid": 1}],
            },
            "0x2222222222222222222222222222222222222222": {
                "positions": [],
                "open_orders": [],
            },
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders", params={"has_open_orders": True})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["traders"]) == 1
        assert data["traders"][0]["has_open_orders"] is True
        assert data["traders"][0]["open_order_count"] == 1

    @pytest.mark.asyncio
    async def test_list_traders_applies_filters_before_pagination(self, app, mock_repository) -> None:
        """Filtered rows should be matched before limit/offset pagination is applied."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0x1111111111111111111111111111111111111111",
                "name": "Flat A",
                "score": 99,
                "tags": [],
                "acct_val": 500000,
                "active": True,
                "performances": {"day": {"roi": 0.1}},
            },
            {
                "eth": "0x2222222222222222222222222222222222222222",
                "name": "Flat B",
                "score": 98,
                "tags": [],
                "acct_val": 500000,
                "active": True,
                "performances": {"day": {"roi": 0.1}},
            },
            {
                "eth": "0x3333333333333333333333333333333333333333",
                "name": "Long C",
                "score": 10,
                "tags": [],
                "acct_val": 500000,
                "active": True,
                "performances": {"day": {"roi": 0.1}},
            },
        ]
        mock_repository.get_trader_current_states.return_value = {
            "0x1111111111111111111111111111111111111111": {"positions": []},
            "0x2222222222222222222222222222222222222222": {"positions": []},
            "0x3333333333333333333333333333333333333333": {
                "positions": [{"position": {"coin": "BTC", "szi": 1}}],
            },
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders",
                params={"limit": 1, "position_status": "long"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["returned_count"] == 1
        assert data["matched_total"] == 1
        assert data["traders"][0]["address"] == "0x3333333333333333333333333333333333333333"

    @pytest.mark.asyncio
    async def test_list_traders_filters_profitable_windows(self, app, mock_repository) -> None:
        """Profitable-window filter should require all requested ROI windows > 0."""
        mock_repository.get_tracked_traders.return_value = [
            {
                "eth": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "name": "Profitable",
                "score": 80,
                "tags": ["consistent"],
                "acct_val": 100000,
                "active": True,
                "performances": {
                    "day": {"roi": 0.05},
                    "week": {"roi": 0.1},
                    "month": {"roi": 0.2},
                },
            },
            {
                "eth": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "name": "Not profitable",
                "score": 81,
                "tags": [],
                "acct_val": 100000,
                "active": True,
                "performances": {
                    "day": {"roi": -0.01},
                    "week": {"roi": 0.1},
                    "month": {"roi": 0.2},
                },
            },
        ]
        mock_repository.get_trader_current_states.return_value = {}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders",
                params={"profitable_windows": "day,week,month"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["returned_count"] == 1
        assert data["traders"][0]["address"] == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    @pytest.mark.asyncio
    async def test_list_traders_no_repository(self, app, mock_lifecycle) -> None:
        """Test list traders when repository is not available."""
        mock_lifecycle.repository = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/traders")

        assert response.status_code == 503
        assert "Repository not available" in response.json()["detail"]


class TestGetTrader:
    """Tests for get_trader endpoint."""

    @pytest.mark.asyncio
    async def test_get_trader_success(self, app, mock_repository) -> None:
        """Test successful get trader response."""
        mock_repository.get_trader_by_address.return_value = {
            "eth": "0x1234567890123456789012345678901234567890",
            "name": "Test Trader",
            "score": 75.5,
            "tags": ["whale"],
            "acct_val": 5000000,
            "active": True,
        }
        mock_repository.get_trader_current_state.return_value = {"positions": []}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["address"] == "0x1234567890123456789012345678901234567890"
        assert data["score"] == 75.5
        assert data["btc_open_orders"] == []

    @pytest.mark.asyncio
    async def test_get_trader_not_found(self, app, mock_repository) -> None:
        """Test get trader when trader not found."""
        mock_repository.get_trader_by_address.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
            )

        assert response.status_code == 404
        assert "Trader not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_trader_with_positions(self, app, mock_repository) -> None:
        """Test get trader with current positions."""
        mock_repository.get_trader_by_address.return_value = {
            "eth": "0x1234567890123456789012345678901234567890",
            "name": "Test Trader",
            "score": 75.5,
            "tags": [],
            "acct_val": 5000000,
            "active": True,
        }
        mock_repository.get_trader_current_state.return_value = {
            "positions": [
                {
                    "position": {
                        "coin": "BTC",
                        "szi": 1.5,
                        "entryPx": 50000,
                        "markPx": 55000,
                        "unrealizedPnl": 5000,
                        "leverage": {"value": 2},
                    }
                }
            ],
            "open_orders": [{"coin": "BTC", "sz": "0.1", "oid": 123}],
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["coin"] == "BTC"
        assert len(data["btc_open_orders"]) == 1


class TestGetTraderOrders:
    """Tests for get_trader_orders endpoint."""

    @pytest.mark.asyncio
    async def test_get_orders_success(self, app, mock_repository) -> None:
        """Current open orders should be returned."""
        mock_repository.get_trader_current_state.return_value = {
            "open_orders": [{"coin": "BTC", "sz": "0.5", "oid": 111}],
            "updated_at": datetime.now(UTC),
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/orders"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["open_orders"][0]["coin"] == "BTC"


class TestGetTraderClosedTrades:
    """Tests for get_trader_closed_trades endpoint."""

    @pytest.mark.asyncio
    async def test_get_closed_trades_success(self, app, mock_repository) -> None:
        """Closed-trades endpoint should return repository rows and count."""
        closed_at = datetime.now(UTC)
        opened_at = closed_at - timedelta(hours=1)
        mock_repository.get_trader_by_address.return_value = {
            "eth": "0x1234567890123456789012345678901234567890",
            "name": "Test Trader",
            "score": 75.5,
            "tags": [],
            "acct_val": 5000000,
            "active": True,
        }
        mock_repository.get_trader_closed_trades.return_value = [
            {
                "trade_id": "trade-1",
                "dir": "long",
                "opened_at": opened_at,
                "closed_at": closed_at,
                "entry_price": 50000,
                "close_reference_price": 51000,
                "max_abs_size": 2.0,
                "final_abs_size": 1.0,
                "last_unrealized_pnl": 1000,
                "close_reason": "flat",
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/closed-trades",
                params={"hours": 24, "limit": 25},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["closed_trades"][0]["trade_id"] == "trade-1"
        assert data["closed_trades"][0]["direction"] == "long"
        mock_repository.get_trader_closed_trades.assert_called_once()
        assert mock_repository.get_trader_closed_trades.call_args.kwargs["limit"] == 25

    @pytest.mark.asyncio
    async def test_get_closed_trades_not_found(self, app, mock_repository) -> None:
        """Unknown tracked traders should return 404 like other trader detail endpoints."""
        mock_repository.get_trader_by_address.return_value = None

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef/closed-trades"
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Trader not found"


class TestGetTraderPositions:
    """Tests for get_trader_positions endpoint."""

    @pytest.mark.asyncio
    async def test_get_positions_success(self, app, mock_repository) -> None:
        """Test successful get positions response."""
        mock_repository.get_trader_positions_history.return_value = [
            {
                "t": datetime.now(UTC),
                "coin": "BTC",
                "sz": 1.5,
                "ep": 50000,
                "mp": 55000,
                "upnl": 5000,
                "lev": 2,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/positions",
                params={"hours": 24},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["positions"]) == 1


class TestGetTraderSignals:
    """Tests for get_trader_signals endpoint."""

    @pytest.mark.asyncio
    async def test_get_signals_success(self, app, mock_repository) -> None:
        """Test successful get signals response."""
        mock_repository.get_trader_signals.return_value = [
            {
                "t": datetime.now(UTC),
                "symbol": "BTC",
                "action": "open",
                "dir": "long",
                "sz": 1.5,
                "conf": 0.85,
            }
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/traders/0x1234567890123456789012345678901234567890/signals",
                params={"hours": 24},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["signals"]) == 1
