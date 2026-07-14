"""Tests for the serial position monitor."""
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from market_scraper.services.monitor import (
    PositionMonitor,
    _parse_leverage,
    _parse_float_or_none,
)
from market_scraper.api import _get_position_status


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.monitor.batch_size = 5
    s.monitor.dwell_seconds = 60
    s.monitor.symbol = "BTC"
    s.monitor.ws_url = "wss://test.hyperliquid.xyz/ws"
    s.monitor.sort_ascending_by_roi = True
    s.monitor.enable_hash_dedup = True
    return s


@pytest.fixture
def monitor(settings: MagicMock) -> PositionMonitor:
    with patch("market_scraper.services.monitor.get_settings", return_value=settings):
        return PositionMonitor()


class TestHelperFunctions:
    def test_parse_leverage_dict(self) -> None:
        assert _parse_leverage({"type": "cross", "value": 10}) == 10.0

    def test_parse_leverage_int(self) -> None:
        assert _parse_leverage(5) == 5.0

    def test_parse_leverage_none(self) -> None:
        assert _parse_leverage(None) == 0.0

    def test_parse_float_or_none_valid(self) -> None:
        assert _parse_float_or_none("50000.5") == 50000.5

    def test_parse_float_or_none_none(self) -> None:
        assert _parse_float_or_none(None) is None

    def test_parse_float_or_none_empty(self) -> None:
        assert _parse_float_or_none("") is None

    def test_parse_float_or_none_invalid(self) -> None:
        assert _parse_float_or_none("notanumber") is None


class TestPositionExtraction:
    def test_webdata2_extracts_btc_positions(self, monitor: PositionMonitor) -> None:
        """Full webData2 message should extract only BTC positions."""
        msg = json.dumps({
            "channel": "webData2",
            "data": {
                "user": "0xtest123",
                "clearinghouseState": {
                    "assetPositions": [
                        {"position": {"coin": "BTC", "szi": "1.5", "entryPx": "50000", "markPx": "51000", "unrealizedPnl": "1500", "leverage": {"type": "cross", "value": 10}, "liquidationPx": "45000"}},
                        {"position": {"coin": "ETH", "szi": "2.0"}},
                    ],
                    "marginSummary": {"accountValue": "100000"},
                },
                "openOrders": [
                    {"coin": "BTC", "sz": "0.5", "oid": 1},
                    {"coin": "ETH", "sz": "1.0", "oid": 2},
                ],
            },
        })

        with patch("market_scraper.services.monitor.get_settings") as mock_settings:
            mock_settings.return_value.monitor.enable_hash_dedup = False
            mock_settings.return_value.monitor.symbol = "BTC"
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db = AsyncMock()
                mock_db.return_value = db

                asyncio.run(monitor._handle_message(msg, "BTC"))

                # Verify trader_current_state was called (upsert)
                assert db.trader_current_state.update_one.call_count == 1
                args, _ = db.trader_current_state.update_one.call_args
                filter_doc = args[0]
                state = args[1]["$set"]
                assert filter_doc == {"eth": "0xtest123"}
                assert len(state["positions"]) == 1  # Only BTC
                assert state["positions"][0]["position"]["coin"] == "BTC"
                assert len(state["open_orders"]) == 1  # Only BTC

    def test_empty_user_skipped(self, monitor: PositionMonitor) -> None:
        msg = json.dumps({"channel": "webData2", "data": {"user": ""}})
        with patch("market_scraper.services.monitor.get_db") as mock_db:
            mock_db.return_value = AsyncMock()
            asyncio.run(monitor._handle_message(msg, "BTC"))
            mock_db.return_value.trader_current_state.update_one.assert_not_called()

    def test_non_webdata2_skipped(self, monitor: PositionMonitor) -> None:
        msg = json.dumps({"channel": "candle", "data": {"o": 1}})
        with patch("market_scraper.services.monitor.get_db") as mock_db:
            mock_db.return_value = AsyncMock()
            asyncio.run(monitor._handle_message(msg, "BTC"))
            mock_db.return_value.trader_current_state.update_one.assert_not_called()


class TestHashDedup:
    def test_same_position_skipped(self, monitor: PositionMonitor) -> None:
        """Same position data with same hash should skip the write."""
        msg = json.dumps({
            "channel": "webData2",
            "data": {
                "user": "0xdedup",
                "clearinghouseState": {
                    "assetPositions": [
                        {"position": {"coin": "BTC", "szi": "1.0"}},
                    ],
                    "marginSummary": {"accountValue": "100000"},
                },
            },
        })

        with patch("market_scraper.services.monitor.get_settings") as mock_settings:
            mock_settings.return_value.monitor.enable_hash_dedup = True
            mock_settings.return_value.monitor.symbol = "BTC"
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db_mock = AsyncMock()
                mock_db.return_value = db_mock

                # Calculate the expected hash
                pos_str = json.dumps(
                    [{"position": {"coin": "BTC", "szi": "1.0"}}],
                    sort_keys=True, separators=(",", ":"),
                )
                ord_str = json.dumps([], sort_keys=True, separators=(",", ":"))
                marg_str = json.dumps(
                    {"accountValue": "100000"},
                    sort_keys=True, separators=(",", ":"),
                )
                expected_hash = hashlib.sha256(
                    (pos_str + ord_str + marg_str).encode()
                ).hexdigest()

                # Existing state has same hash
                db_mock.trader_current_state.find_one = AsyncMock(
                    return_value={"position_hash": expected_hash}
                )

                asyncio.run(monitor._handle_message(msg, "BTC"))

                # update_one should NOT be called (same hash)
                db_mock.trader_current_state.update_one.assert_not_called()
                db_mock.trader_positions.insert_one.assert_not_called()

    def test_different_position_saved(self, monitor: PositionMonitor) -> None:
        """Different position data should trigger a write."""
        msg = json.dumps({
            "channel": "webData2",
            "data": {
                "user": "0xchange",
                "clearinghouseState": {
                    "assetPositions": [
                        {"position": {"coin": "BTC", "szi": "2.0"}},
                    ],
                    "marginSummary": {"accountValue": "100000"},
                },
            },
        })

        with patch("market_scraper.services.monitor.get_settings") as mock_settings:
            mock_settings.return_value.monitor.enable_hash_dedup = True
            mock_settings.return_value.monitor.symbol = "BTC"
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db_mock = AsyncMock()
                mock_db.return_value = db_mock

                # Different hash
                db_mock.trader_current_state.find_one = AsyncMock(
                    return_value={"position_hash": "old_hash_123"}
                )

                asyncio.run(monitor._handle_message(msg, "BTC"))

                # update_one SHOULD be called (different hash)
                db_mock.trader_current_state.update_one.assert_called_once()
                db_mock.trader_positions.insert_one.assert_called_once()


class TestParseOrder:
    def test_flat_position_detected(self) -> None:
        assert _get_position_status({"positions": []}) == "flat"

    def test_long_position_detected(self) -> None:
        assert _get_position_status({"positions": [{"position": {"szi": "1.5"}}]}) == "long"

    def test_short_position_detected(self) -> None:
        assert _get_position_status({"positions": [{"position": {"szi": "-2.0"}}]}) == "short"

    def test_mixed_positions_detected(self) -> None:
        assert _get_position_status({"positions": [
            {"position": {"szi": "1.0"}},
            {"position": {"szi": "-0.5"}},
        ]}) == "mixed"

    def test_unknown_state(self) -> None:
        assert _get_position_status(None) == "unknown"

    def test_no_positions_key(self) -> None:
        assert _get_position_status({}) == "unknown"
