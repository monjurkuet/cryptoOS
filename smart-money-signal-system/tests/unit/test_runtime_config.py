from pathlib import Path

from signal_system.runtime_config import SignalRuntimeConfigStore


def test_runtime_config_status_exposes_checksum_and_version(tmp_path: Path):
    config_path = tmp_path / "signal_system.yaml"
    store = SignalRuntimeConfigStore(config_path)
    store.load()

    status = store.status()

    assert status["config_path"] == str(config_path)
    assert status["config_version"] == 1
    assert isinstance(status["checksum_sha256"], str)
    assert len(status["checksum_sha256"]) == 64
    assert status["modified_at"] is not None


def test_runtime_config_history_tracks_updates(tmp_path: Path):
    config_path = tmp_path / "signal_system.yaml"
    store = SignalRuntimeConfigStore(config_path)
    config = store.load()
    config.config_version = 2
    store.save(config)

    history = store.get_history(limit=10)
    assert len(history) >= 1
    assert history[0]["config_version"] == 2
    assert isinstance(history[0]["checksum_sha256"], str)
