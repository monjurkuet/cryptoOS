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

    def test_custom_values(self) -> None:
        """Test custom MongoDB configuration."""
        config = MongoConfig(
            url="mongodb+srv://cluster0.example.mongodb.net/",
            database="market_scraper",
            max_pool_size=20,
            min_pool_size=2,
        )
        assert config.url == "mongodb+srv://cluster0.example.mongodb.net/"
        assert config.database == "market_scraper"
        assert config.max_pool_size == 20
        assert config.min_pool_size == 2


class TestSettings:
    """Test suite for Settings."""

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults(self) -> None:
        """Test default settings."""
        settings = Settings(_env_file=None, mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert settings.app_name == "market-scraper"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.environment == "development"
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 3845
        assert settings.mongo.url == "mongodb+srv://example.mongodb.net/"

    @patch.dict(os.environ, {}, clear=True)
    def test_nested_configs(self) -> None:
        """Test nested configuration objects."""
        settings = Settings(_env_file=None, mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert isinstance(settings.redis, RedisConfig)
        assert isinstance(settings.mongo, MongoConfig)
        assert isinstance(settings.logging, LoggingConfig)
        assert settings.mongo.url == "mongodb+srv://example.mongodb.net/"

    @patch.dict(
        os.environ,
        {"APP_NAME": "test-app"},
        clear=False,
    )
    def test_env_override(self) -> None:
        """Test environment variable override."""
        settings = Settings(mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert settings.app_name == "test-app"

    @patch.dict(
        os.environ,
        {
            "REDIS__URL": "redis://custom:6379",
        },
        clear=False,
    )
    def test_nested_env_override(self) -> None:
        """Test nested environment variable override."""
        settings = Settings(mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert settings.redis.url == "redis://custom:6379"
        assert settings.mongo.url == "mongodb+srv://example.mongodb.net/"

    def test_custom_values(self) -> None:
        """Test custom settings values."""
        settings = Settings(
            app_name="custom-scraper",
            app_version="1.0.0",
            debug=True,
            environment="production",
            api_port=9000,
            mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"),
        )
        assert settings.app_name == "custom-scraper"
        assert settings.app_version == "1.0.0"
        assert settings.debug is True
        assert settings.environment == "production"
        assert settings.api_port == 9000
        assert settings.mongo.url == "mongodb+srv://example.mongodb.net/"

    @patch.dict(
        os.environ,
        {"DEBUG": "release"},
        clear=False,
    )
    def test_legacy_release_debug_value(self) -> None:
        """Legacy release/debug strings should not crash settings parsing."""
        settings = Settings(mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert settings.debug is False

    @patch.dict(
        os.environ,
        {"DEBUG": "debug"},
        clear=False,
    )
    def test_legacy_debug_string_enables_debug(self) -> None:
        """The legacy 'debug' string should map to True."""
        settings = Settings(mongo=MongoConfig(url="mongodb+srv://example.mongodb.net/"))
        assert settings.debug is True


class TestGetSettings:
    """Test suite for get_settings function."""

    @patch.dict(
        os.environ,
        {"MONGO__URL": "mongodb+srv://example.mongodb.net/"},
        clear=False,
    )
    def test_singleton(self) -> None:
        """Test that get_settings returns cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    @patch.dict(
        os.environ,
        {"MONGO__URL": "mongodb+srv://example.mongodb.net/"},
        clear=False,
    )
    def test_cache_clear(self) -> None:
        """Test cache clear functionality."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # They should be equal but not the same object
        assert settings1 is not settings2
        assert settings1.app_name == settings2.app_name
