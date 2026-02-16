"""
Rate Limit Manager.

Adapted from ~/development/hyperliquid for managing API rate limits.
"""

import asyncio
import time
from enum import Enum
from typing import Optional


class RateLimitState(Enum):
    """Rate limit state enumeration."""

    NORMAL = "normal"
    SLOWING = "slowing"
    RECOVERING = "recovering"


class RateLimitManager:
    """
    Manages rate limiting detection and adaptive responses.

    Detects rate limiting patterns and automatically adjusts behavior.
    """

    def __init__(
        self,
        error_threshold: int = 3,
        recovery_time: int = 300,
        max_error_count: int = 6,
    ):
        """
        Initialize the rate limit manager.

        Args:
            error_threshold: Number of errors before slowing down
            recovery_time: Time in seconds of clean operation before recovery
            max_error_count: Maximum errors before entering recovery mode
        """
        self.state = RateLimitState.NORMAL
        self.error_threshold = error_threshold
        self.recovery_time = recovery_time
        self.max_error_count = max_error_count

        # State tracking
        self.error_count = 0
        self.last_error_time = 0
        self.last_success_time = time.time()
        self.consecutive_successes = 0

        self._lock = asyncio.Lock()

    async def report_connection_error(self, error_type: str = "connection") -> None:
        """Report a connection error for rate limit detection."""
        async with self._lock:
            self.error_count += 1
            self.last_error_time = time.time()
            self.consecutive_successes = 0

            # Update state based on error count
            await self._update_state_from_errors()

    async def report_success(self) -> None:
        """Report a successful operation for recovery tracking."""
        async with self._lock:
            self.last_success_time = time.time()
            self.consecutive_successes += 1

            # Check for recovery potential
            if self.state != RateLimitState.NORMAL:
                time_since_last_error = time.time() - self.last_error_time

                if time_since_last_error > self.recovery_time and self.consecutive_successes >= 5:
                    await self._recover_to_normal()

    def get_delay_multiplier(self) -> float:
        """
        Get the current delay multiplier for rate limiting.

        Returns:
            Multiplier to apply to all delays (1.0 = normal, >1.0 = slower)
        """
        if self.state == RateLimitState.NORMAL:
            return 1.0
        elif self.state == RateLimitState.SLOWING:
            return 2.0  # Double the delays
        else:  # RECOVERING
            return 4.0  # Quadruple the delays

    async def get_adaptive_delay(self, base_delay: float) -> float:
        """
        Get adaptive delay based on current state.

        Args:
            base_delay: Base delay time

        Returns:
            Adjusted delay time
        """
        multiplier = self.get_delay_multiplier()
        return base_delay * multiplier

    def should_throttle(self) -> bool:
        """
        Determine if we should throttle connections.

        Returns:
            True if connections should be throttled
        """
        # Throttle if we've had multiple recent errors
        recent_errors = self._get_recent_error_count()
        return recent_errors >= 2

    def get_backoff_delay(self, base_delay: float) -> float:
        """
        Get exponential backoff delay for immediate retries.

        Args:
            base_delay: Base delay in seconds

        Returns:
            Backoff delay in seconds
        """
        # Exponential backoff based on error count
        backoff_factor = min(2 ** (self.error_count - 1), 16)  # Max 16x
        return base_delay * backoff_factor

    async def reset(self) -> None:
        """Reset the rate limit manager to normal state."""
        async with self._lock:
            self.state = RateLimitState.NORMAL
            self.error_count = 0
            self.last_error_time = 0
            self.last_success_time = time.time()
            self.consecutive_successes = 0

    async def _update_state_from_errors(self) -> None:
        """Update rate limit state based on current error count."""
        if self.error_count >= self.max_error_count:
            if self.state != RateLimitState.RECOVERING:
                self.state = RateLimitState.RECOVERING

        elif self.error_count >= self.error_threshold:
            if self.state != RateLimitState.SLOWING:
                self.state = RateLimitState.SLOWING

    async def _recover_to_normal(self) -> None:
        """Recover to normal operation state."""
        if self.state != RateLimitState.NORMAL:
            # Reduce error count gradually for recovery
            self.error_count = max(0, self.error_count - 2)
            self.state = RateLimitState.NORMAL

    def _get_recent_error_count(self) -> int:
        """Get count of errors in the last 60 seconds."""
        if time.time() - self.last_error_time > 60:
            return 0
        return self.error_count

    def get_status_summary(self) -> dict:
        """Get a summary of current rate limit status."""
        return {
            "state": self.state.value,
            "error_count": self.error_count,
            "consecutive_successes": self.consecutive_successes,
            "delay_multiplier": self.get_delay_multiplier(),
            "time_since_last_error": time.time() - self.last_error_time
            if self.last_error_time > 0
            else 0,
        }


# Global instance
rate_limit_manager = RateLimitManager()
