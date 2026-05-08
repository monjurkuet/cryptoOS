"""Signal Generation Processor."""

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import structlog

from signal_system.utils.safe_convert import safe_float

logger = structlog.get_logger(__name__)

# Default TTL for trader data (24 hours in seconds)
TRADER_TTL_SECONDS = 86400
# Maximum number of traders to track
MAX_TRACKED_TRADERS = 10000

DEFAULT_PARAM_RANGES: dict[str, tuple[float, float]] = {
    "bias_threshold": (0.05, 0.8),
    "conf_scale": (0.1, 3.0),
    "min_confidence": (0.05, 0.9),
}


class SignalGenerationProcessor:
    """Generates trading signals from trader position data.

    Implements TTL-based cleanup to prevent unbounded memory growth.
    Traders that haven't been updated in 24 hours are automatically removed.

    RL-adjustable parameters:
        bias_threshold: Net bias threshold for BUY/SELL (default 0.2)
        conf_scale: Multiplier for confidence calculation (default 1.0)
        min_confidence: Minimum confidence to emit a signal (default 0.0)
    """

    def __init__(
        self,
        symbol: str = "BTC",
        trader_ttl_seconds: int = TRADER_TTL_SECONDS,
        max_traders: int = MAX_TRACKED_TRADERS,
        bias_threshold: float = 0.2,
        conf_scale: float = 1.0,
        min_confidence: float = 0.0,
        emit_bias_delta: float = 0.1,
        decision_trace_buffer_size: int = 1000,
        parameter_ranges: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        """Initialize the processor.

        Args:
            symbol: Trading symbol to generate signals for
            trader_ttl_seconds: TTL for trader data in seconds
            max_traders: Maximum number of traders to track
            bias_threshold: Net bias threshold for BUY/SELL recommendation
            conf_scale: Scaling factor for confidence calculation
            min_confidence: Minimum confidence to emit a signal
        """
        self.symbol = symbol
        self._trader_ttl = trader_ttl_seconds
        self._max_traders = max_traders
        self._emit_bias_delta = emit_bias_delta

        # RL-adjustable parameters
        self._bias_threshold = bias_threshold
        self._conf_scale = conf_scale
        self._min_confidence = min_confidence
        self._param_ranges = parameter_ranges or dict(DEFAULT_PARAM_RANGES)

        # State with TTL tracking: address -> (data, last_access_time)
        self._trader_positions: dict[str, tuple[dict, float]] = {}
        self._trader_scores: dict[str, float] = {}
        self._last_signal: dict | None = None
        self._last_decision_trace: dict[str, Any] | None = None
        self._decision_traces: deque[dict[str, Any]] = deque(
            maxlen=max(100, decision_trace_buffer_size)
        )
        self._signals_generated = 0

    async def process_position(self, event: dict) -> dict | None:
        """Process trader position event.

        Args:
            event: Raw event from market-scraper

        Returns:
            Generated signal if significant change, else None
        """
        payload = event.get("payload", {})
        address = payload.get("address")

        if not address:
            return None

        # Store position with timestamp
        self._trader_positions[address] = (payload, time.time())

        # Cleanup stale traders periodically
        self._cleanup_stale_traders()

        # Generate signal
        return self._generate_signal()

    async def process_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event containing trader scores
        """
        payload = event.get("payload", {})
        traders = payload.get("traders", [])

        for trader in traders:
            address = trader.get("address")
            score = trader.get("score", 50)
            if address:
                self._trader_scores[address] = score

    def _cleanup_stale_traders(self) -> None:
        """Remove traders that haven't been updated recently.

        Called on each position update to ensure memory doesn't grow unbounded.
        """
        now = time.time()
        cutoff = now - self._trader_ttl

        # Remove stale traders
        stale_addresses = [
            addr for addr, (_, last_access) in self._trader_positions.items()
            if last_access < cutoff
        ]

        for addr in stale_addresses:
            del self._trader_positions[addr]
            # Also remove scores for stale traders
            self._trader_scores.pop(addr, None)

        if stale_addresses:
            logger.debug(
                "trader_cleanup",
                removed=len(stale_addresses),
                remaining=len(self._trader_positions),
            )

        # Enforce max size limit (LRU eviction)
        if len(self._trader_positions) > self._max_traders:
            sorted_items = sorted(
                self._trader_positions.items(),
                key=lambda x: x[1][1],  # Sort by last_access time
            )
            for addr, _ in sorted_items[:len(self._trader_positions) - self._max_traders]:
                del self._trader_positions[addr]
                self._trader_scores.pop(addr, None)

    def _generate_signal(self) -> dict | None:
        """Generate aggregated signal.

        Returns:
            Signal dict if significant, else None
        """
        if not self._trader_positions:
            return None

        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        traders_long = 0
        traders_short = 0

        for address, (position, _) in self._trader_positions.items():
            score = self._trader_scores.get(address, 50)
            weight = score / 100

            # Get BTC position
            positions = position.get("positions", [])
            btc_position = None

            for pos in positions:
                pos_data = pos.get("position", pos)
                if pos_data.get("coin") == self.symbol:
                    btc_position = pos_data
                    break

            if btc_position:
                szi = safe_float(btc_position.get("szi"), 0)

                if szi > 0:
                    long_score += weight
                    traders_long += 1
                elif szi < 0:
                    short_score += weight
                    traders_short += 1

                total_weight += weight

        if total_weight == 0:
            return None

        long_bias = long_score / total_weight
        short_bias = short_score / total_weight
        net_bias = long_bias - short_bias

        # Determine action using RL-adjustable bias threshold
        if net_bias > self._bias_threshold:
            action = "BUY"
        elif net_bias < -self._bias_threshold:
            action = "SELL"
        else:
            action = "NEUTRAL"

        # Compute confidence with RL-adjustable scale
        raw_confidence = abs(net_bias) * 2
        scaled_confidence = min(raw_confidence * self._conf_scale, 1.0)

        signal = {
            "symbol": self.symbol,
            "action": action,
            "confidence": scaled_confidence,
            "long_bias": round(long_bias, 4),
            "short_bias": round(short_bias, 4),
            "net_bias": round(net_bias, 4),
            "traders_long": traders_long,
            "traders_short": traders_short,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        reason_code = "emit"
        result = "emitted"

        if action == "NEUTRAL":
            reason_code = "threshold_not_met"

        # Only emit if confidence meets minimum threshold
        if scaled_confidence < self._min_confidence:
            reason_code = "min_confidence_not_met"
            result = "suppressed"
            self._record_decision_trace(
                weighted_long_score=long_score,
                weighted_short_score=short_score,
                total_weight=total_weight,
                net_bias=net_bias,
                raw_confidence=raw_confidence,
                scaled_confidence=scaled_confidence,
                action=action,
                result=result,
                reason_code=reason_code,
            )
            return None

        # Only emit if different from last signal
        if self._should_emit(signal):
            self._last_signal = signal
            self._signals_generated += 1
            self._record_decision_trace(
                weighted_long_score=long_score,
                weighted_short_score=short_score,
                total_weight=total_weight,
                net_bias=net_bias,
                raw_confidence=raw_confidence,
                scaled_confidence=scaled_confidence,
                action=action,
                result=result,
                reason_code=reason_code,
            )
            return signal

        self._record_decision_trace(
            weighted_long_score=long_score,
            weighted_short_score=short_score,
            total_weight=total_weight,
            net_bias=net_bias,
            raw_confidence=raw_confidence,
            scaled_confidence=scaled_confidence,
            action=action,
            result="suppressed",
            reason_code="duplicate_signal",
        )
        return None

    def _record_decision_trace(
        self,
        weighted_long_score: float,
        weighted_short_score: float,
        total_weight: float,
        net_bias: float,
        raw_confidence: float,
        scaled_confidence: float,
        action: str,
        result: str,
        reason_code: str,
        store: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc)
        trace = {
            "timestamp": now.isoformat(),
            "timestamp_ts": now.timestamp(),
            "symbol": self.symbol,
            "tracked_traders": len(self._trader_positions),
            "scored_traders": len(self._trader_scores),
            "bias_threshold": round(self._bias_threshold, 8),
            "conf_scale": round(self._conf_scale, 8),
            "min_confidence": round(self._min_confidence, 8),
            "weighted_long_score": round(weighted_long_score, 8),
            "weighted_short_score": round(weighted_short_score, 8),
            "total_weight": round(total_weight, 8),
            "net_bias": round(net_bias, 8),
            "raw_confidence": round(raw_confidence, 8),
            "scaled_confidence": round(scaled_confidence, 8),
            "action": action,
            "result": result,
            "reason_code": reason_code,
        }
        if store:
            self._last_decision_trace = trace
            self._decision_traces.append(trace)

    def _should_emit(self, signal: dict) -> bool:
        """Check if signal should be emitted.

        Args:
            signal: New signal to check

        Returns:
            True if signal should be emitted
        """
        if self._last_signal is None:
            return True

        if signal["action"] != self._last_signal.get("action"):
            return True

        bias_change = abs(signal["net_bias"] - self._last_signal.get("net_bias", 0))
        return bias_change >= self._emit_bias_delta

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dict with processor stats
        """
        return {
            "signals_generated": self._signals_generated,
            "tracked_traders": len(self._trader_positions),
            "scored_traders": len(self._trader_scores),
            "decision_traces": len(self._decision_traces),
            "rl_params": {
                "bias_threshold": self._bias_threshold,
                "conf_scale": self._conf_scale,
                "min_confidence": self._min_confidence,
                "emit_bias_delta": self._emit_bias_delta,
            },
        }

    def set_rl_params(
        self,
        bias_threshold: float | None = None,
        conf_scale: float | None = None,
        min_confidence: float | None = None,
    ) -> None:
        """Update RL-adjustable parameters at runtime.

        Called by the ParameterServer when new params are available
        after a training run.

        Args:
            bias_threshold: New bias threshold (or None to keep current)
            conf_scale: New confidence scale (or None to keep current)
            min_confidence: New minimum confidence (or None to keep current)
        """
        if bias_threshold is not None:
            self._bias_threshold = self._clamp_param("bias_threshold", bias_threshold)
        if conf_scale is not None:
            self._conf_scale = self._clamp_param("conf_scale", conf_scale)
        if min_confidence is not None:
            self._min_confidence = self._clamp_param("min_confidence", min_confidence)

        logger.debug(
            "signal_processor_rl_params_updated",
            bias_threshold=self._bias_threshold,
            conf_scale=self._conf_scale,
            min_confidence=self._min_confidence,
        )

    def set_runtime_config(
        self,
        symbol: str | None = None,
        trader_ttl_seconds: int | None = None,
        max_traders: int | None = None,
        emit_bias_delta: float | None = None,
        decision_trace_buffer_size: int | None = None,
        parameter_ranges: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        """Update runtime behavior without recreating the processor."""
        if symbol:
            self.symbol = symbol
        if trader_ttl_seconds is not None:
            self._trader_ttl = max(1, trader_ttl_seconds)
        if max_traders is not None:
            self._max_traders = max(100, max_traders)
        if emit_bias_delta is not None:
            self._emit_bias_delta = max(0.0, emit_bias_delta)
        if parameter_ranges is not None:
            self._param_ranges = dict(parameter_ranges)
        if decision_trace_buffer_size is not None:
            buffer_size = max(100, decision_trace_buffer_size)
            self._decision_traces = deque(self._decision_traces, maxlen=buffer_size)

    def get_latest_signal(self) -> dict | None:
        """Get the latest generated signal.

        Returns:
            Latest signal or None
        """
        return self._last_signal

    def get_latest_decision_trace(self) -> dict[str, Any] | None:
        """Get latest decision trace for explainability."""
        return self._last_decision_trace

    def get_decision_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent decision traces."""
        return list(self._decision_traces)[-limit:]

    def _clamp_param(self, key: str, value: float) -> float:
        lo, hi = self._param_ranges.get(key, DEFAULT_PARAM_RANGES[key])
        return max(lo, min(hi, value))
