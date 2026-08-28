"""Tests for the serial REST position monitor."""
import asyncio
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from market_scraper.api import _get_position_status
from market_scraper.services.monitor import (
    PositionMonitor,
    _parse_float_or_none,
    _parse_leverage,
)


@pytest.fixture
def settings() -> MagicMock:
    s = MagicMock()
    s.monitor.batch_size = 5
    s.monitor.dwell_seconds = 60
    s.monitor.symbol = "BTC"
    s.monitor.ws_url = "wss://api.hyperliquid.xyz/ws"
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


class TestPositionStorage:
    def test_store_btc_positions(self, monitor: PositionMonitor) -> None:
        """REST response with BTC position should be stored correctly."""
        data = {
            "marginSummary": {"accountValue": "100000"},
            "assetPositions": [
                {"position": {"coin": "BTC", "szi": "1.5", "entryPx": "50000", "markPx": "51000", "unrealizedPnl": "1500", "leverage": {"type": "cross", "value": 10}, "liquidationPx": "45000"}},
                {"position": {"coin": "ETH", "szi": "2.0"}},
            ],
        }

        orig_dedup = monitor.settings.monitor.enable_hash_dedup
        monitor.settings.monitor.enable_hash_dedup = False
        try:
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db = AsyncMock()
                mock_db.return_value = db

                asyncio.run(monitor._store_state("0xtest123", data, "BTC"))

                # Verify trader_current_state was called
                assert db.trader_current_state.update_one.call_count == 1
                args, _ = db.trader_current_state.update_one.call_args
                state = args[1]["$set"]
                assert state["eth"] == "0xtest123"
                assert len(state["positions"]) == 1  # Only BTC
                assert state["positions"][0]["position"]["coin"] == "BTC"
        finally:
            monitor.settings.monitor.enable_hash_dedup = orig_dedup

    def test_empty_positions_stored(self, monitor: PositionMonitor) -> None:
        """REST response with no BTC positions should still store flat state."""
        data = {
            "marginSummary": {"accountValue": "100000"},
            "assetPositions": [
                {"position": {"coin": "ETH", "szi": "2.0"}},
            ],
        }

        orig_dedup = monitor.settings.monitor.enable_hash_dedup
        monitor.settings.monitor.enable_hash_dedup = False
        try:
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db = AsyncMock()
                mock_db.return_value = db

                asyncio.run(monitor._store_state("0xtest", data, "BTC"))

                args, _ = db.trader_current_state.update_one.call_args
                state = args[1]["$set"]
                assert state["positions"] == []  # No BTC
        finally:
            monitor.settings.monitor.enable_hash_dedup = orig_dedup

    def test_empty_user_skipped(self, monitor: PositionMonitor) -> None:
        with patch("market_scraper.services.monitor.get_db") as mock_db:
            mock_db.return_value = AsyncMock()
            # _store_state with empty eth should not crash
            asyncio.run(monitor._store_state("", {}, "BTC"))


class TestHashDedup:
    def test_same_position_skipped(self, monitor: PositionMonitor) -> None:
        """Same position data with same hash should skip the write."""
        data = {
            "marginSummary": {"accountValue": "100000"},
            "assetPositions": [
                {"position": {"coin": "BTC", "szi": "1.0"}},
            ],
        }

        with patch("market_scraper.services.monitor.get_settings") as mock_settings:
            mock_settings.return_value.monitor.enable_hash_dedup = True
            mock_settings.return_value.monitor.symbol = "BTC"
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db_mock = AsyncMock()
                mock_db.return_value = db_mock

                # Calculate expected hash
                pos_str = json.dumps(
                    [{"position": {"coin": "BTC", "szi": "1.0"}}],
                    sort_keys=True, separators=(",", ":"),
                )
                marg_str = json.dumps(
                    {"accountValue": "100000"},
                    sort_keys=True, separators=(",", ":"),
                )
                expected_hash = hashlib.sha256(
                    (pos_str + marg_str).encode()
                ).hexdigest()

                db_mock.trader_current_state.find_one = AsyncMock(
                    return_value={"position_hash": expected_hash}
                )

                asyncio.run(monitor._store_state("0xdedup", data, "BTC"))

                # update_one should NOT be called (same hash)
                db_mock.trader_current_state.update_one.assert_not_called()
                db_mock.trader_positions.insert_one.assert_not_called()

    def test_different_position_saved(self, monitor: PositionMonitor) -> None:
        """Different position data should trigger a write."""
        data = {
            "marginSummary": {"accountValue": "100000"},
            "assetPositions": [
                {"position": {"coin": "BTC", "szi": "2.0"}},
            ],
        }

        with patch("market_scraper.services.monitor.get_settings") as mock_settings:
            mock_settings.return_value.monitor.enable_hash_dedup = True
            mock_settings.return_value.monitor.symbol = "BTC"
            with patch("market_scraper.services.monitor.get_db") as mock_db:
                db_mock = AsyncMock()
                mock_db.return_value = db_mock

                db_mock.trader_current_state.find_one = AsyncMock(
                    return_value={"position_hash": "old_hash_123"}
                )

                asyncio.run(monitor._store_state("0xchange", data, "BTC"))

                db_mock.trader_current_state.update_one.assert_called_once()
                db_mock.trader_positions.insert_one.assert_called_once()


class TestPositionStatus:
    def test_flat(self) -> None:
        assert _get_position_status({"positions": []}) == "flat"

    def test_long(self) -> None:
        assert _get_position_status({"positions": [{"position": {"szi": "1.5"}}]}) == "long"

    def test_short(self) -> None:
        assert _get_position_status({"positions": [{"position": {"szi": "-2.0"}}]}) == "short"

    def test_mixed(self) -> None:
        assert _get_position_status({"positions": [
            {"position": {"szi": "1.0"}},
            {"position": {"szi": "-0.5"}},
        ]}) == "mixed"

    def test_unknown(self) -> None:
        assert _get_position_status(None) == "unknown"

    def test_no_positions_key(self) -> None:
        assert _get_position_status({}) == "unknown"
