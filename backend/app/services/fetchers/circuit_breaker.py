"""
Circuit Breaker Pattern for Data Source Fault Tolerance

Prevents cascading failures when a data source is down by
automatically switching to backup sources.
"""
import time
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"   # Normal operation, requests go through
    OPEN = "open"       # Failure threshold exceeded, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and request is rejected"""
    def __init__(self, source_name: str, message: str = ""):
        self.source_name = source_name
        self.message = message or f"Circuit breaker is open for {source_name}"
        super().__init__(self.message)


class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance"""
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds before trying again
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold  # successes needed in half-open to close


class CircuitBreaker:
    """
    Circuit breaker implementation per data source.

    State machine:
    CLOSED → (failure_threshold reached) → OPEN
    OPEN → (recovery_timeout elapsed) → HALF_OPEN
    HALF_OPEN → (success_threshold successes) → CLOSED
    HALF_OPEN → (any failure) → OPEN
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout-based transition"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    logger.info(f"[CircuitBreaker] {self.name}: OPEN → HALF_OPEN (timeout elapsed)")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
        return self._state

    def record_success(self):
        """Record a successful call"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                logger.info(f"[CircuitBreaker] {self.name}: HALF_OPEN → CLOSED (recovered)")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success in closed state
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed call"""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately opens circuit
            logger.warning(f"[CircuitBreaker] {self.name}: HALF_OPEN → OPEN (failure in test)")
            self._state = CircuitState.OPEN
            self._success_count = 0
            self._half_open_calls = 0

        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                logger.warning(f"[CircuitBreaker] {self.name}: CLOSED → OPEN (failures={self._failure_count})")
                self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a request can be executed"""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls
        # OPEN: reject
        return False

    def before_call(self):
        """Call before executing a request; raises CircuitBreakerOpen if blocked"""
        state = self.state
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(self.name)
        if state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1

    def get_status(self) -> dict:
        """Return circuit breaker status for debugging/admin"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_calls": self._half_open_calls,
            "last_failure_age_seconds": (
                time.monotonic() - self._last_failure_time
                if self._last_failure_time else None
            ),
        }


class CircuitContext:
    """Context manager for circuit breaker protection"""

    def __init__(self, breaker: CircuitBreaker, source_name: str):
        self.breaker = breaker
        self.source_name = source_name
        self.result = None
        self.error = None

    def __enter__(self):
        self.breaker.before_call()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception = failure
            self.error = exc_val
            self.breaker.record_failure()
            logger.warning(f"[CircuitBreaker] {self.source_name} call failed: {exc_val}")
        else:
            self.breaker.record_success()
            logger.debug(f"[CircuitBreaker] {self.source_name} call succeeded")
        return False  # Don't suppress exceptions
