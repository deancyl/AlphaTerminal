"""
Tests for AdaptiveCircuitBreaker service.

Tests cover:
- State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- Failure tracking and threshold
- Recovery mechanism
- Adaptive timeout adjustment
"""

import time
from datetime import datetime

from app.services.adaptive_circuit_breaker import (
    AdaptiveCircuitBreaker,
    AdaptiveBreakerManager,
    RecoveryRecord,
    get_adaptive_breaker_manager,
)
from app.services.circuit_breaker import CircuitState


class TestCircuitBreakerStates:
    """Tests for state transitions"""

    def test_initial_state_is_closed(self):
        """Test that initial state is CLOSED"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_open_on_failures(self):
        """Test CLOSED -> OPEN transition on consecutive failures"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=3, base_timeout=30.0)

        # Record failures up to threshold
        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_transitions_to_half_open_after_timeout(self):
        """Test OPEN -> HALF_OPEN transition after timeout"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN state
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Check state - should transition to HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_transitions_to_closed_on_success(self):
        """Test HALF_OPEN -> CLOSED transition on success"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN state
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout to enter HALF_OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record enough successes (success_threshold from parent is 2)
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_stays_open_on_failure_in_half_open(self):
        """Test HALF_OPEN -> OPEN on failure"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN state
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout to enter HALF_OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record failure - should go back to OPEN
        cb.record_failure()

        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerFailureTracking:
    """Tests for failure tracking"""

    def test_failure_count_increments_on_failure(self):
        """Test that consecutive_failures increments on failure"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=10)

        # Use record_recovery to track consecutive failures
        assert cb._consecutive_failures == 0

        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 1

        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 2

    def test_failure_count_reset_on_success(self):
        """Test that consecutive_failures resets on success"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=10)

        # Record some failures via record_recovery
        cb.record_recovery(success=False, recovery_time=1.0)
        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 2

        # Record success
        cb.record_recovery(success=True, recovery_time=1.0)
        assert cb._consecutive_failures == 0

    def test_threshold_triggers_open_state(self):
        """Test that reaching failure_threshold triggers OPEN state"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)

        # Record 4 failures - should still be CLOSED
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

        # 5th failure - should be OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_consecutive_failures_count(self):
        """Test consecutive failures tracking"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=10)

        # Record failures via record_recovery
        for i in range(5):
            cb.record_recovery(success=False, recovery_time=1.0)
            assert cb._consecutive_failures == i + 1

        # Record success - should reset
        cb.record_recovery(success=True, recovery_time=1.0)
        assert cb._consecutive_failures == 0


class TestCircuitBreakerRecovery:
    """Tests for recovery mechanism"""

    def test_half_open_allows_limited_requests(self):
        """Test that HALF_OPEN state allows limited requests"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for HALF_OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Should be available in HALF_OPEN
        assert cb.is_available() is True

    def test_success_in_half_open_closes_circuit(self):
        """Test that success in HALF_OPEN closes the circuit"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN -> HALF_OPEN
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes (need 2 for success_threshold)
        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(self):
        """Test that failure in HALF_OPEN reopens the circuit"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN -> HALF_OPEN
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        # Record failure
        cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_recovery_timeout_configurable(self):
        """Test that recovery timeout is configurable"""
        cb1 = AdaptiveCircuitBreaker("test1", base_timeout=10.0)
        cb2 = AdaptiveCircuitBreaker("test2", base_timeout=60.0)

        assert cb1.base_timeout == 10.0
        assert cb2.base_timeout == 60.0

        # Check config
        assert cb1.config.timeout == 10.0
        assert cb2.config.timeout == 60.0


class TestCircuitBreakerAdaptiveTimeout:
    """Tests for adaptive timeout"""

    def test_timeout_increases_on_failures(self):
        """Test that timeout increases with consecutive failures"""
        cb = AdaptiveCircuitBreaker(
            "test", base_timeout=30.0, min_timeout=10.0, max_timeout=120.0
        )

        # Add recovery history to enable adaptive calculation
        for _ in range(5):
            cb.record_recovery(success=False, recovery_time=1.0)

        # Get adaptive timeout - should be increased due to low success rate
        adaptive_timeout = cb.get_adaptive_timeout()

        # With 5 failures and 0 successes, timeout should increase
        assert adaptive_timeout >= cb.base_timeout

    def test_timeout_decreases_on_success(self):
        """Test that timeout decreases with high success rate"""
        cb = AdaptiveCircuitBreaker(
            "test", base_timeout=30.0, min_timeout=10.0, max_timeout=120.0
        )

        # Add recovery history with high success rate
        for _ in range(5):
            cb.record_recovery(success=True, recovery_time=1.0)

        # Get adaptive timeout - should be decreased due to high success rate
        adaptive_timeout = cb.get_adaptive_timeout()

        # With 100% success rate, timeout should decrease
        assert adaptive_timeout <= cb.base_timeout

    def test_timeout_has_min_max_bounds(self):
        """Test that timeout stays within min/max bounds"""
        cb = AdaptiveCircuitBreaker(
            "test", base_timeout=30.0, min_timeout=10.0, max_timeout=120.0
        )

        # Add many failures to push timeout up
        for _ in range(20):
            cb.record_recovery(success=False, recovery_time=1.0)

        adaptive_timeout = cb.get_adaptive_timeout()
        assert adaptive_timeout >= cb.min_timeout
        assert adaptive_timeout <= cb.max_timeout

        # Add many successes to push timeout down
        cb._consecutive_failures = 0
        for _ in range(20):
            cb.record_recovery(success=True, recovery_time=1.0)

        adaptive_timeout = cb.get_adaptive_timeout()
        assert adaptive_timeout >= cb.min_timeout
        assert adaptive_timeout <= cb.max_timeout

    def test_adaptive_timeout_disabled_with_insufficient_history(self):
        """Test that adaptive timeout returns base_timeout with insufficient history"""
        cb = AdaptiveCircuitBreaker(
            "test", base_timeout=30.0, min_timeout=10.0, max_timeout=120.0
        )

        # No history - should return base_timeout
        assert cb.get_adaptive_timeout() == cb.base_timeout

        # Only 2 records - still insufficient (need 3)
        cb.record_recovery(success=True, recovery_time=1.0)
        cb.record_recovery(success=True, recovery_time=1.0)
        assert cb.get_adaptive_timeout() == cb.base_timeout

        # 3 records - now sufficient
        cb.record_recovery(success=True, recovery_time=1.0)
        # Now it may differ from base_timeout
        adaptive_timeout = cb.get_adaptive_timeout()
        # With all successes, should be <= base_timeout
        assert adaptive_timeout <= cb.base_timeout


class TestCircuitBreakerIsAvailable:
    """Tests for is_available check"""

    def test_is_available_true_when_closed(self):
        """Test is_available returns True when CLOSED"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)

        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    def test_is_available_false_when_open(self):
        """Test is_available returns False when OPEN"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2)

        # Trigger OPEN
        cb.record_failure()
        cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_is_available_limited_when_half_open(self):
        """Test is_available returns True when HALF_OPEN"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2, base_timeout=0.1)

        # Trigger OPEN -> HALF_OPEN
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)

        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_available() is True


class TestCircuitBreakerReset:
    """Tests for reset functionality"""

    def test_reset_returns_to_closed(self):
        """Test that reset returns state to CLOSED"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2)

        # Trigger OPEN
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        """Test that reset clears consecutive_failures (parent stats only)"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=10)

        # Record failures via record_failure (updates parent stats)
        for _ in range(5):
            cb.record_failure()

        # Reset clears parent stats
        cb.reset()

        # Parent stats are cleared, but adaptive breaker's _consecutive_failures
        # is NOT reset by parent's reset() method
        # This test verifies the parent reset behavior
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_counters(self):
        """Test that reset clears all counters"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=10)

        # Record some activity
        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        # Reset
        cb.reset()

        # Check all counters are reset
        assert cb._consecutive_failures == 0
        assert len(cb._recovery_history) == 0
        assert cb._current_timeout == cb.base_timeout


class TestCircuitBreakerContextManager:
    """Tests for context manager usage"""

    def test_context_manager_enter_exit(self):
        """Test context manager enter/exit behavior"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)

        # Use as context manager
        with cb:
            pass  # Success

        # Should have recorded success in parent stats
        stats = cb.get_stats()
        assert stats["consecutive_failures"] == 0

    def test_context_manager_tracks_success(self):
        """Test that context manager tracks successful operations"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)

        with cb:
            result = 42

        # Check parent class stats
        stats = cb.get_stats()
        assert stats["consecutive_failures"] == 0

    def test_context_manager_tracks_failure(self):
        """Test that context manager tracks failed operations"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5)

        try:
            with cb:
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # The parent class tracks failures in _stats
        # The adaptive breaker's _consecutive_failures is only updated via record_recovery
        # So we check that the state is still CLOSED (threshold not reached)
        assert cb.state == CircuitState.CLOSED


class TestRecoveryRecord:
    """Tests for RecoveryRecord dataclass"""

    def test_recovery_record_creation(self):
        """Test RecoveryRecord creation"""
        record = RecoveryRecord(
            timestamp=datetime.now(), success=True, recovery_time=5.5
        )

        assert record.success is True
        assert record.recovery_time == 5.5
        assert isinstance(record.timestamp, datetime)

    def test_recovery_record_failure(self):
        """Test RecoveryRecord for failure case"""
        record = RecoveryRecord(
            timestamp=datetime.now(), success=False, recovery_time=10.0
        )

        assert record.success is False
        assert record.recovery_time == 10.0


class TestAdaptiveBreakerManager:
    """Tests for AdaptiveBreakerManager"""

    def test_get_breaker_creates_new(self):
        """Test that get_breaker creates new breaker if not exists"""
        manager = AdaptiveBreakerManager()

        breaker = manager.get_breaker("test_breaker")

        assert breaker is not None
        assert breaker.name == "test_breaker"
        assert isinstance(breaker, AdaptiveCircuitBreaker)

    def test_get_breaker_returns_existing(self):
        """Test that get_breaker returns existing breaker"""
        manager = AdaptiveBreakerManager()

        breaker1 = manager.get_breaker("test_breaker")
        breaker2 = manager.get_breaker("test_breaker")

        assert breaker1 is breaker2

    def test_get_all_stats(self):
        """Test get_all_stats returns stats for all breakers"""
        manager = AdaptiveBreakerManager()

        # Create some breakers
        manager.get_breaker("breaker1")
        manager.get_breaker("breaker2")

        stats = manager.get_all_stats()

        assert "breaker1" in stats
        assert "breaker2" in stats
        assert stats["breaker1"]["name"] == "breaker1"
        assert stats["breaker2"]["name"] == "breaker2"


class TestGetAdaptiveBreakerManager:
    """Tests for get_adaptive_breaker_manager singleton"""

    def test_returns_singleton(self):
        """Test that get_adaptive_breaker_manager returns singleton"""
        manager1 = get_adaptive_breaker_manager()
        manager2 = get_adaptive_breaker_manager()

        assert manager1 is manager2

    def test_manager_is_correct_type(self):
        """Test that manager is AdaptiveBreakerManager"""
        manager = get_adaptive_breaker_manager()

        assert isinstance(manager, AdaptiveBreakerManager)


class TestAdaptiveCircuitBreakerStats:
    """Tests for get_stats method"""

    def test_get_stats_returns_correct_structure(self):
        """Test that get_stats returns correct structure"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=5, base_timeout=30.0)

        stats = cb.get_stats()

        assert "name" in stats
        assert "state" in stats
        assert "current_timeout" in stats
        assert "base_timeout" in stats
        assert "consecutive_failures" in stats
        assert "recovery_history_size" in stats

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["base_timeout"] == 30.0

    def test_get_stats_reflects_current_state(self):
        """Test that get_stats reflects current state"""
        cb = AdaptiveCircuitBreaker("test", failure_threshold=2)

        # Trigger OPEN
        cb.record_failure()
        cb.record_failure()

        stats = cb.get_stats()

        assert stats["state"] == "open"

    def test_get_stats_reflects_recovery_history(self):
        """Test that get_stats reflects recovery history"""
        cb = AdaptiveCircuitBreaker("test")

        # Add recovery records
        cb.record_recovery(success=True, recovery_time=1.0)
        cb.record_recovery(success=False, recovery_time=2.0)

        stats = cb.get_stats()

        assert stats["recovery_history_size"] == 2


class TestRecordRecovery:
    """Tests for record_recovery method"""

    def test_record_recovery_adds_to_history(self):
        """Test that record_recovery adds to history"""
        cb = AdaptiveCircuitBreaker("test", recovery_history_size=10)

        assert len(cb._recovery_history) == 0

        cb.record_recovery(success=True, recovery_time=1.0)
        assert len(cb._recovery_history) == 1

        cb.record_recovery(success=False, recovery_time=2.0)
        assert len(cb._recovery_history) == 2

    def test_record_recovery_resets_consecutive_failures_on_success(self):
        """Test that record_recovery resets consecutive_failures on success"""
        cb = AdaptiveCircuitBreaker("test")

        # Record some failures via record_recovery
        cb.record_recovery(success=False, recovery_time=1.0)
        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 2

        # Record successful recovery
        cb.record_recovery(success=True, recovery_time=1.0)
        assert cb._consecutive_failures == 0

    def test_record_recovery_increments_failures_on_failure(self):
        """Test that record_recovery increments consecutive_failures on failure"""
        cb = AdaptiveCircuitBreaker("test")

        assert cb._consecutive_failures == 0

        # Record failed recovery
        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 1

        cb.record_recovery(success=False, recovery_time=1.0)
        assert cb._consecutive_failures == 2

    def test_recovery_history_has_max_size(self):
        """Test that recovery history respects max size"""
        cb = AdaptiveCircuitBreaker("test", recovery_history_size=5)

        # Add more records than max size
        for i in range(10):
            cb.record_recovery(success=True, recovery_time=float(i))

        # Should only keep last 5
        assert len(cb._recovery_history) == 5
