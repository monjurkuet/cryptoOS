# tests/unit/connectors/test_base.py

"""Unit tests for connector base classes."""

import pytest
from pydantic import ValidationError

from market_scraper.connectors.base import ConnectorConfig, DataConnector
from market_scraper.connectors.registry import ConnectorRegistry


class TestConnectorConfig:
    """Test ConnectorConfig model."""

    def test_valid_config(self) -> None:
        """Test creating a valid config."""
        config = ConnectorConfig(name="test_connector")
        assert config.name == "test_connector"
        assert config.enabled is True
        assert config.rate_limit_per_second == 10.0
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 1.0

    def test_config_with_custom_values(self) -> None:
        """Test config with custom values."""
        config = ConnectorConfig(
            name="custom",
            enabled=False,
            rate_limit_per_second=5.0,
            timeout_seconds=60.0,
            max_retries=5,
            retry_delay_seconds=2.0,
        )
        assert config.name == "custom"
        assert config.enabled is False
        assert config.rate_limit_per_second == 5.0
        assert config.timeout_seconds == 60.0
        assert config.max_retries == 5
        assert config.retry_delay_seconds == 2.0

    def test_config_missing_name(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError):
            ConnectorConfig()


class TestConnectorRegistry:
    """Test ConnectorRegistry."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        ConnectorRegistry.clear()

    def teardown_method(self) -> None:
        """Clear registry after each test."""
        ConnectorRegistry.clear()

    def test_register_connector(self) -> None:
        """Test registering a connector."""

        class TestConnector(DataConnector):
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_historical_data(self, symbol, timeframe, start, end):
                return []

            async def stream_realtime(self, symbols):
                yield None  # type: ignore

            async def health_check(self):
                return {"status": "healthy"}

        ConnectorRegistry.register("test", TestConnector)
        assert "test" in ConnectorRegistry.list_connectors()

    def test_get_connector(self) -> None:
        """Test getting a registered connector."""

        class TestConnector(DataConnector):
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_historical_data(self, symbol, timeframe, start, end):
                return []

            async def stream_realtime(self, symbols):
                yield None  # type: ignore

            async def health_check(self):
                return {"status": "healthy"}

        ConnectorRegistry.register("test", TestConnector)
        retrieved = ConnectorRegistry.get("test")
        assert retrieved is TestConnector

    def test_get_unknown_connector(self) -> None:
        """Test getting an unknown connector raises KeyError."""
        with pytest.raises(KeyError, match="Unknown connector: unknown"):
            ConnectorRegistry.get("unknown")

    def test_list_connectors_empty(self) -> None:
        """Test listing connectors when empty."""
        assert ConnectorRegistry.list_connectors() == []

    def test_register_duplicate_name_different_class(self) -> None:
        """Test registering duplicate name with different class raises error."""

        class TestConnector1(DataConnector):
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_historical_data(self, symbol, timeframe, start, end):
                return []

            async def stream_realtime(self, symbols):
                yield None  # type: ignore

            async def health_check(self):
                return {"status": "healthy"}

        class TestConnector2(DataConnector):
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_historical_data(self, symbol, timeframe, start, end):
                return []

            async def stream_realtime(self, symbols):
                yield None  # type: ignore

            async def health_check(self):
                return {"status": "healthy"}

        ConnectorRegistry.register("test", TestConnector1)
        with pytest.raises(ValueError, match="already registered"):
            ConnectorRegistry.register("test", TestConnector2)

    def test_register_same_class_ok(self) -> None:
        """Test registering same name with same class is OK."""

        class TestConnector(DataConnector):
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def get_historical_data(self, symbol, timeframe, start, end):
                return []

            async def stream_realtime(self, symbols):
                yield None  # type: ignore

            async def health_check(self):
                return {"status": "healthy"}

        ConnectorRegistry.register("test", TestConnector)
        # Should not raise
        ConnectorRegistry.register("test", TestConnector)
        assert ConnectorRegistry.list_connectors() == ["test"]
