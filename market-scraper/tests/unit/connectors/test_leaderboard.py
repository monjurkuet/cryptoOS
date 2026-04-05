"""Tests for LeaderboardCollector."""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from market_scraper.connectors.hyperliquid.collectors.leaderboard import LeaderboardCollector
from market_scraper.config.market_config import MarketConfig, StorageConfig, FilterConfig
from market_scraper.core.config import HyperliquidSettings


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Create mock event bus."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Create mock repository with leaderboard/trader persistence methods."""
    repo = AsyncMock()
    repo.store_leaderboard_snapshot = AsyncMock(return_value=True)
    repo.upsert_tracked_trader_data = AsyncMock(return_value=True)
    repo.deactivate_unselected_traders = AsyncMock(return_value=0)
    repo.get_active_trader_addresses = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_config() -> HyperliquidSettings:
    """Create test configuration."""
    return HyperliquidSettings(
        symbol="BTC",
    )


@pytest.fixture
def mock_market_config() -> MarketConfig:
    """Create mock market config."""
    return MarketConfig(
        storage=StorageConfig(
            refresh_interval=3600,
            keep_snapshots=True,
        ),
        filters=FilterConfig(
            min_score=50,
            max_count=500,
            min_account_value=10000,
        ),
    )


class TestLeaderboardCollector:
    """Tests for LeaderboardCollector class."""

    def test_init(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test initialization."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        assert collector.event_bus == mock_event_bus
        assert collector.config == mock_config
        assert collector._running is False
        assert collector._refresh_interval == 3600

    def test_init_custom_refresh_interval(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test initialization with custom refresh interval."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
            refresh_interval=7200,
        )

        assert collector._refresh_interval == 7200

    @pytest.mark.asyncio
    async def test_start(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test starting the collector."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        # Mock the refresh loop
        with patch.object(collector, "_refresh_loop_with_initial", new_callable=AsyncMock):
            await collector.start()

            assert collector._running is True
            assert collector._session is not None

            # Cleanup
            await collector.stop()

    @pytest.mark.asyncio
    async def test_stop(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test stopping the collector."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        # Start first
        with patch.object(collector, "_refresh_loop_with_initial", new_callable=AsyncMock):
            await collector.start()
            await collector.stop()

            assert collector._running is False

    def test_get_stats(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test getting collector stats."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        collector._fetches = 5
        collector._errors = 1
        collector._last_tracked_count = 100

        stats = collector.get_stats()

        assert stats["running"] is False
        assert stats["fetches"] == 5
        assert stats["errors"] == 1

    def test_calculate_score(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test trader score calculation."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        trader_data = {
            "winningDays": 20,
            "winRate": 0.65,
        }

        score = collector._calculate_score(trader_data)

        assert isinstance(score, (int, float))

    def test_apply_filters(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Test filter application."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        # Use correct key names from implementation
        traders = [
            {"eth": "0x1", "score": 80, "acct_val": 100000},
            {"eth": "0x2", "score": 30, "acct_val": 50000},  # Below min_score
            {"eth": "0x3", "score": 90, "acct_val": 5000},  # Below min_account_value
        ]

        filtered = collector._apply_filters(traders)

        assert len(filtered) == 1
        assert filtered[0]["eth"] == "0x1"

    @pytest.mark.asyncio
    async def test_fetch_publishes_canonical_leaderboard_event(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Collector publishes canonical leaderboard event payload."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        sample_rows = [
            {
                "ethAddress": "0x1234567890123456789012345678901234567890",
                "displayName": "trader-1",
                "accountValue": 1000000,
                "windowPerformances": [["allTime", {"roi": 1.2}], ["month", {"roi": 0.3}]],
            }
        ]

        collector._session = MagicMock()
        collector._fetch_leaderboard = AsyncMock(return_value={"leaderboardRows": sample_rows})

        await collector._fetch_and_process()

        mock_event_bus.publish.assert_awaited_once()
        event = mock_event_bus.publish.call_args.args[0]
        assert str(event.event_type) == "leaderboard"
        assert event.payload["rows"] == sample_rows
        assert event.payload["traders"] == sample_rows

    @pytest.mark.asyncio
    async def test_get_tracked_addresses_uses_repository(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Tracked addresses are resolved via repository abstraction."""
        mock_repository.get_active_trader_addresses.return_value = [
            "0x1234567890123456789012345678901234567890",
            "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
        ]

        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        addresses = await collector.get_tracked_addresses()
        assert len(addresses) == 2
        mock_repository.get_active_trader_addresses.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_derived_data_uses_repository_flow(
        self,
        mock_event_bus: MagicMock,
        mock_config: HyperliquidSettings,
        mock_market_config: MarketConfig,
        mock_repository: AsyncMock,
    ) -> None:
        """Collector persists tracked traders and deactivation set via repository."""
        collector = LeaderboardCollector(
            event_bus=mock_event_bus,
            config=mock_config,
            repository=mock_repository,
            market_config=mock_market_config,
        )

        tracked = [
            {"eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0001", "score": 81, "acct_val": 20000},
            {"eth": "0xABCDEFabcdefABCDEFabcdefABCDEFabcdef0002", "score": 75, "acct_val": 15000},
        ]

        await collector._store_derived_data(traders=tracked, total_count=42)

        assert mock_repository.upsert_tracked_trader_data.await_count == 2
        first_payload = mock_repository.upsert_tracked_trader_data.await_args_list[0].args[0]
        second_payload = mock_repository.upsert_tracked_trader_data.await_args_list[1].args[0]
        assert first_payload["eth"] == "0xabcdefabcdefabcdefabcdefabcdefabcdef0001"
        assert second_payload["eth"] == "0xabcdefabcdefabcdefabcdefabcdefabcdef0002"

        mock_repository.deactivate_unselected_traders.assert_awaited_once()
        selected_addresses = mock_repository.deactivate_unselected_traders.await_args.kwargs[
            "selected_addresses"
        ]
        assert selected_addresses == [
            "0xabcdefabcdefabcdefabcdefabcdefabcdef0001",
            "0xabcdefabcdefabcdefabcdefabcdefabcdef0002",
        ]


class TestLeaderboardScoring:
    """Tests for scoring logic."""

    def test_score_with_roi(self) -> None:
        """Test scoring with ROI data."""
        collector = LeaderboardCollector(
            event_bus=MagicMock(),
            config=HyperliquidSettings(),
        )

        trader = {
            "winningDays": 30,
            "winRate": 0.70,
            "roi": 0.50,  # 50% ROI
            "acct_val": 1_000_000,
        }

        score = collector._calculate_score(trader)

        # Score should be a valid number
        assert isinstance(score, (int, float))

    def test_score_with_negative_roi(self) -> None:
        """Test scoring with negative ROI."""
        collector = LeaderboardCollector(
            event_bus=MagicMock(),
            config=HyperliquidSettings(),
        )

        trader = {
            "winningDays": 10,
            "winRate": 0.40,
            "roi": -0.20,  # -20% ROI
            "acct_val": 100_000,
        }

        score = collector._calculate_score(trader)

        # Score should be a valid number
        assert isinstance(score, (int, float))
