"""YAML-backed runtime configuration for the signal system."""

from __future__ import annotations

from pathlib import Path
from hashlib import sha256
from datetime import UTC, datetime
import threading
from typing import Any

from pydantic import BaseModel, Field, field_validator
import yaml


class RangeConfig(BaseModel):
    """Numeric range configuration."""

    min: float
    max: float

    def clamp(self, value: float) -> float:
        return max(self.min, min(self.max, value))


class SignalParameterDefaultsConfig(BaseModel):
    """Default live signal parameters."""

    bias_threshold: float = 0.2
    conf_scale: float = 1.0
    min_confidence: float = 0.3


class SignalParameterRangesConfig(BaseModel):
    """Allowed live signal parameter ranges."""

    bias_threshold: RangeConfig = Field(default_factory=lambda: RangeConfig(min=0.05, max=0.8))
    conf_scale: RangeConfig = Field(default_factory=lambda: RangeConfig(min=0.1, max=3.0))
    min_confidence: RangeConfig = Field(default_factory=lambda: RangeConfig(min=0.05, max=0.9))


class SignalParameterConfig(BaseModel):
    """Signal parameter defaults and valid ranges."""

    defaults: SignalParameterDefaultsConfig = Field(default_factory=SignalParameterDefaultsConfig)
    ranges: SignalParameterRangesConfig = Field(default_factory=SignalParameterRangesConfig)


class SignalProcessorRuntimeConfig(BaseModel):
    """Signal processor runtime settings."""

    symbol: str = "BTC"
    trader_ttl_seconds: int = 86400
    max_traders: int = 10000
    emit_bias_delta: float = 0.1
    decision_trace_buffer_size: int = 1000


class OutcomeTrackingConfig(BaseModel):
    """Outcome tracker runtime settings."""

    evaluation_horizons: list[int] = Field(default_factory=lambda: [60, 300, 900, 3600])
    max_pending: int = 10000
    max_outcomes: int = 50000

    @field_validator("evaluation_horizons", mode="before")
    @classmethod
    def normalize_horizons(cls, value: Any) -> list[int]:
        if not isinstance(value, list):
            return [60, 300, 900, 3600]
        horizons = sorted({int(item) for item in value if int(item) > 0})
        return horizons or [60, 300, 900, 3600]


class PerformanceWeightRuntimeConfig(BaseModel):
    sharpe_weight: float = 0.25
    sortino_weight: float = 0.20
    consistency_weight: float = 0.20
    max_drawdown_weight: float = 0.15
    win_rate_weight: float = 0.10
    profit_factor_weight: float = 0.10


class SizeWeightRuntimeConfig(BaseModel):
    alpha_whale_threshold: float = 20_000_000
    whale_threshold: float = 10_000_000
    large_threshold: float = 5_000_000
    medium_threshold: float = 1_000_000
    standard_threshold: float = 100_000
    alpha_whale_weight: float = 3.0
    whale_weight: float = 2.5
    large_weight: float = 2.0
    medium_weight: float = 1.5
    standard_weight: float = 1.0
    small_weight: float = 0.5


class RecencyWeightRuntimeConfig(BaseModel):
    day_weight: float = 0.50
    week_weight: float = 0.30
    month_weight: float = 0.20
    min_recency: float = 0.5
    max_recency: float = 1.5


class WeightingRuntimeConfig(BaseModel):
    performance: PerformanceWeightRuntimeConfig = Field(default_factory=PerformanceWeightRuntimeConfig)
    size: SizeWeightRuntimeConfig = Field(default_factory=SizeWeightRuntimeConfig)
    recency: RecencyWeightRuntimeConfig = Field(default_factory=RecencyWeightRuntimeConfig)
    performance_dimension_weight: float = 0.40
    size_dimension_weight: float = 0.30
    recency_dimension_weight: float = 0.20
    regime_dimension_weight: float = 0.10


class WhaleAlertRuntimeConfig(BaseModel):
    """Whale alert detector runtime settings."""

    alpha_whale_threshold: float = 20_000_000
    whale_threshold: float = 10_000_000
    aggregation_window_minutes: int = 5
    position_history_ttl: int = 604800
    max_alerts: int = 500
    max_recent_changes: int = 1000


class ImprovementRuntimeConfig(BaseModel):
    """Signal improvement and retraining runtime settings."""

    enable_retrain_api: bool = False
    load_checkpoint_on_startup: bool = False
    checkpoint_dir: str = "checkpoints"
    default_retrain_episodes: int = 100


class SignalRuntimeConfig(BaseModel):
    """Top-level signal runtime configuration."""

    config_version: int = 1
    signal_processor: SignalProcessorRuntimeConfig = Field(default_factory=SignalProcessorRuntimeConfig)
    parameters: SignalParameterConfig = Field(default_factory=SignalParameterConfig)
    outcome_tracking: OutcomeTrackingConfig = Field(default_factory=OutcomeTrackingConfig)
    weighting: WeightingRuntimeConfig = Field(default_factory=WeightingRuntimeConfig)
    whale_alerts: WhaleAlertRuntimeConfig = Field(default_factory=WhaleAlertRuntimeConfig)
    improvement: ImprovementRuntimeConfig = Field(default_factory=ImprovementRuntimeConfig)
    dashboard_retention_days: int = 30


class SignalRuntimeConfigStore:
    """Thread-safe YAML config loader/saver for signal runtime settings."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._history_path = path.with_suffix(f"{path.suffix}.history.yaml")
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def validate(self, payload: dict[str, Any]) -> SignalRuntimeConfig:
        return SignalRuntimeConfig.model_validate(payload)

    def load(self) -> SignalRuntimeConfig:
        with self._lock:
            if not self._path.exists():
                config = SignalRuntimeConfig()
                self._write(config)
                return config
            with self._path.open("r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
            return SignalRuntimeConfig.model_validate(raw)

    def save(self, config: SignalRuntimeConfig) -> SignalRuntimeConfig:
        with self._lock:
            self._write(config)
            return config

    def save_payload(self, payload: dict[str, Any]) -> SignalRuntimeConfig:
        config = self.validate(payload)
        return self.save(config)

    def status(self) -> dict[str, Any]:
        with self._lock:
            config = self.load()
            content = self._path.read_text(encoding="utf-8") if self._path.exists() else ""
            checksum = sha256(content.encode("utf-8")).hexdigest()
            stat = self._path.stat() if self._path.exists() else None
            modified_at = (
                datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat() if stat is not None else None
            )
            return {
                "config_path": str(self._path),
                "config_version": config.config_version,
                "checksum_sha256": checksum,
                "modified_at": modified_at,
            }

    def _write(self, config: SignalRuntimeConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        config_payload = config.model_dump(mode="json")
        with temp_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(config_payload, handle, sort_keys=False)
        temp_path.replace(self._path)
        self._append_history(config_payload)

    def _append_history(self, config_payload: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        checksum = sha256(yaml.safe_dump(config_payload, sort_keys=False).encode("utf-8")).hexdigest()
        event = {
            "timestamp": now,
            "config_version": config_payload.get("config_version"),
            "checksum_sha256": checksum,
        }
        history: list[dict[str, Any]] = []
        if self._history_path.exists():
            try:
                with self._history_path.open("r", encoding="utf-8") as handle:
                    history = yaml.safe_load(handle) or []
            except Exception:
                history = []
        history.insert(0, event)
        history = history[:200]
        temp_path = self._history_path.with_suffix(f"{self._history_path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(history, handle, sort_keys=False)
        temp_path.replace(self._history_path)

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            if not self._history_path.exists():
                return []
            with self._history_path.open("r", encoding="utf-8") as handle:
                history = yaml.safe_load(handle) or []
            return history[: max(1, min(limit, 200))]
