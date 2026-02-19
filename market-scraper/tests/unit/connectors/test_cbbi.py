# tests/unit/connectors/test_cbbi.py

"""Unit tests for CBBI connector skeleton."""

from market_scraper.connectors.base import ConnectorConfig, DataConnector
from market_scraper.connectors.cbbi import (
    CBBIClient,
    CBBIConfig,
    CBBIConnector,
    parse_cbbi_component_response,
    parse_cbbi_historical_response,
    parse_cbbi_index_response,
    parse_timestamp,
    validate_cbbi_data,
)


class TestCBBIConfig:
    """Test suite for CBBIConfig."""

    def test_cbbi_config_inherits_from_connector_config(self):
        """Test that CBBIConfig inherits from ConnectorConfig."""
        assert issubclass(CBBIConfig, ConnectorConfig)

    def test_cbbi_config_creation(self):
        """Test that CBBIConfig can be instantiated with defaults."""
        config = CBBIConfig(name="cbbi")
        assert config.name == "cbbi"
        assert config.enabled is True
        assert config.rate_limit_per_second == 10.0
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 1.0
        # CBBI-specific fields
        assert str(config.base_url) == "https://colintalkscrypto.com/cbbi/data"
        assert config.api_key is None
        assert config.update_interval_seconds == 86400  # 24 hours - CBBI updates daily
        assert config.historical_days == 365
        assert config.metrics_enabled is True


class TestCBBIClient:
    """Test suite for CBBIClient skeleton."""

    def test_cbbi_client_exists(self):
        """Test that CBBIClient class exists."""
        assert CBBIClient is not None

    def test_cbbi_client_initialization(self):
        """Test that CBBIClient can be initialized."""
        config = CBBIConfig(name="cbbi")
        client = CBBIClient(config)
        assert client.config == config

    def test_cbbi_client_methods_exist(self):
        """Test that all expected CBBIClient methods exist."""
        config = CBBIConfig(name="cbbi")
        client = CBBIClient(config)

        assert hasattr(client, "connect")
        assert hasattr(client, "close")
        assert hasattr(client, "get_index_data")
        assert hasattr(client, "get_historical_data")
        assert hasattr(client, "get_component_data")
        assert hasattr(client, "health_check")


class TestCBBIConnector:
    """Test suite for CBBIConnector."""

    def test_cbbi_connector_inherits_from_data_connector(self):
        """Test that CBBIConnector inherits from DataConnector."""
        assert issubclass(CBBIConnector, DataConnector)

    def test_cbbi_connector_initialization(self):
        """Test that CBBIConnector can be initialized."""
        config = CBBIConfig(name="cbbi")
        connector = CBBIConnector(config)
        assert connector.name == "cbbi"
        assert connector.is_connected is False
        assert connector.config == config

    def test_cbbi_connector_abstract_methods_exist(self):
        """Test that all abstract methods are implemented (even if just stubs)."""
        config = CBBIConfig(name="cbbi")
        connector = CBBIConnector(config)

        assert hasattr(connector, "connect")
        assert hasattr(connector, "disconnect")
        assert hasattr(connector, "get_historical_data")
        assert hasattr(connector, "stream_realtime")
        assert hasattr(connector, "health_check")

    def test_cbbi_connector_additional_methods_exist(self):
        """Test that CBBI-specific methods exist."""
        config = CBBIConfig(name="cbbi")
        connector = CBBIConnector(config)

        assert hasattr(connector, "get_current_index")
        assert hasattr(connector, "get_component_breakdown")


class TestCBBIParsers:
    """Test suite for CBBI parser functions."""

    def test_parse_cbbi_index_response_exists(self):
        """Test that parse_cbbi_index_response function exists."""
        assert callable(parse_cbbi_index_response)

    def test_parse_cbbi_historical_response_exists(self):
        """Test that parse_cbbi_historical_response function exists."""
        assert callable(parse_cbbi_historical_response)

    def test_parse_cbbi_component_response_exists(self):
        """Test that parse_cbbi_component_response function exists."""
        assert callable(parse_cbbi_component_response)

    def test_parse_timestamp_exists(self):
        """Test that parse_timestamp function exists."""
        assert callable(parse_timestamp)

    def test_validate_cbbi_data_exists(self):
        """Test that validate_cbbi_data function exists."""
        assert callable(validate_cbbi_data)


class TestCBBIImports:
    """Test that all CBBI components can be imported."""

    def test_all_exports_available(self):
        """Test that all exports in __all__ are available."""
        from market_scraper.connectors.cbbi import __all__

        assert "CBBIClient" in __all__
        assert "CBBIConfig" in __all__
        assert "CBBIConnector" in __all__
        assert "parse_cbbi_component_response" in __all__
        assert "parse_cbbi_historical_response" in __all__
        assert "parse_cbbi_index_response" in __all__
        assert "parse_timestamp" in __all__
        assert "validate_cbbi_data" in __all__
