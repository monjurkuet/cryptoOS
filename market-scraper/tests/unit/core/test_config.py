# tests/unit/core/test_config.py

"""Test suite for configuration management."""

import os
from unittest.mock import patch

import pytest

from market_scraper.core.config import (
    LoggingConfig,
    MongoConfig,
    RedisConfig,
    Settings,
    get_settings,
)


class TestLoggingConfig:
    """Test suite for LoggingConfig."""

    def test_default_level(self) -> None:
        """Test default log level is INFO."""
        config = LoggingConfig()
        assert config.level == "INFO"

    def test_valid_levels(self) -> None:
        """Test valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level

        # Test lowercase
        for level in ["debug", "info", "warning", "error", "critical"]:
            config = LoggingConfig(level=level)
            assert config.level == level.upper()

    def test_invalid_level(self) -> None:
        """Test invalid log level raises error."""
        with pytest.raises(ValueError, match="Invalid log level"):
            LoggingConfig(level="INVALID")


class TestRedisConfig:
    """Test suite for RedisConfig."""

    def test_defaults(self) -> None:
        """Test default Redis configuration."""
        config = RedisConfig()
        assert config.url == "redis://localhost:6379"
        assert config.max_connections == 10
        assert config.socket_timeout == 5.0
        assert config.socket_connect_timeout == 5.0

    def test_custom_values(self) -> None:
        """Test custom Redis configuration."""
        config = RedisConfig(
            url="redis://custom-host:6380",
            max_connections=20,
            socket_timeout=10.0,
            socket_connect_timeout=10.0,
        )
        assert config.url == "redis://custom-host:6380"
        assert config.max_connections == 20
        assert config.socket_timeout == 10.0
        assert config.socket_connect_timeout == 10.0


class TestMongoConfig:
    """Test suite for MongoConfig."""

    def test_defaults(self) -> None:
        """Test default MongoDB configuration."""
        config = MongoConfig()
        assert config.url == "mongodb://localhost:27017"
        assert config.database == "market_scraper"
        assert config.max_pool_size == 10
        assert config.min_pool_size == 1


class TestSettings:
    """Test suite for Settings."""

    def test_defaults(self) -> None:
        """Test default settings."""
        settings = Settings()
        assert settings.app_name == "market-scraper"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000

    def test_nested_configs(self) -> None:
        """Test nested configuration objects."""
        settings = Settings()
        assert isinstance(settings.redis, RedisConfig)
        assert isinstance(settings.mongo, MongoConfig)
        assert isinstance(settings.logging, LoggingConfig)

    @patch.dict(os.environ, {"APP_NAME": "test-app"}, clear=False)
    def test_env_override(self) -> None:
        """Test environment variable override."""
        settings = Settings()
        assert settings.app_name == "test-app"

    @patch.dict(os.environ, {"REDIS__URL": "redis://custom:6379"}, clear=False)
    def test_nested_env_override(self) -> None:
        """Test nested environment variable override."""
        settings = Settings()
        assert settings.redis.url == "redis://custom:6379"

    def test_custom_values(self) -> None:
        """Test custom settings values."""
        settings = Settings(
            app_name="custom-scraper",
            app_version="1.0.0",
            debug=True,
            environment="production",
            api_port=9000,
        )
        assert settings.app_name == "custom-scraper"
        assert settings.app_version == "1.0.0"
        assert settings.debug is True
        assert settings.environment == "production"
        assert settings.api_port == 9000


class TestGetSettings:
    """Test suite for get_settings function."""

    def test_singleton(self) -> None:
        """Test that get_settings returns cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_cache_clear(self) -> None:
        """Test cache clear functionality."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # They should be equal but not the same object
        assert settings1 is not settings2
        assert settings1.app_name == settings2.app_name
