"""Tests for API root path configuration."""

from pathlib import Path

from signal_system.config import SignalSystemSettings


def test_api_root_path_default():
    settings = SignalSystemSettings()
    assert settings.api_root_path == "/signal-system"


def test_api_root_path_normalization_adds_leading_slash(monkeypatch):
    monkeypatch.setenv("API_ROOT_PATH", "signal-system/")
    settings = SignalSystemSettings()
    assert settings.api_root_path == "/signal-system"


def test_api_root_path_normalization_allows_root(monkeypatch):
    monkeypatch.setenv("API_ROOT_PATH", "/")
    settings = SignalSystemSettings()
    assert settings.api_root_path == ""


def test_fastapi_app_sets_root_path_from_settings():
    main_file = Path(__file__).parents[2] / "src" / "signal_system" / "api" / "main.py"
    assert "root_path=settings.api_root_path" in main_file.read_text()
