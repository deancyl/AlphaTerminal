"""
Circuit Breaker Tests

Tests for the circuit breaker implementation in backend/app/services/circuit_breaker.py
Covers both CircuitBreaker and SlidingWindowCircuitBreaker classes.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpen,
    SlidingWindowCircuitBreaker,
    SlidingWindowConfig,
)


class TestCircuitBreaker:
    """Tests for the traditional CircuitBreaker (consecutive failure threshold)."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker with test configuration."""
        return CircuitBreaker(
            "test_breaker",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=30.0,
                half_open_max_calls=3
            )
        )
    
    def test_initial_state_is_closed(self, circuit_breaker):
        """Circuit breaker should start in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._stats.consecutive_failures == 0
    
    def test_record_success_resets_failure_count(self, circuit_breaker):
        """Recording success should reset failure count."""
        circuit_breaker._stats.consecutive_failures = 3
        circuit_breaker.record_success()
        assert circuit_breaker._stats.consecutive_failures == 0
    
    def test_record_failure_increments_count(self, circuit_breaker):
        """Recording failure should increment failure count."""
        circuit_breaker.record_failure()
        assert circuit_breaker._stats.consecutive_failures == 1
    
    def test_opens_after_threshold_failures(self, circuit_breaker):
        """Circuit breaker should OPEN after reaching failure threshold."""
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
    
    def test_allows_call_when_closed(self, circuit_breaker):
        """Should allow calls when in CLOSED state."""
        assert circuit_breaker.is_available() is True
    
    def test_blocks_call_when_open(self, circuit_breaker):
        """Should block calls when in OPEN state."""
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.is_available() is False
    
    def test_transitions_to_half_open_after_timeout(self, circuit_breaker):
        """Should transition to HALF_OPEN after recovery timeout."""
        # Force OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Simulate timeout by modifying internal state
        circuit_breaker._opened_at = time.time() - 31
        
        # Check state should transition to HALF_OPEN
        assert circuit_breaker.state == CircuitState.HALF_OPEN
    
    def test_half_open_to_closed_on_success(self, circuit_breaker):
        """Should transition from HALF_OPEN to CLOSED on success."""
        # Force HALF_OPEN state
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._stats.consecutive_successes = 1
        
        circuit_breaker.record_success()
        
        assert circuit_breaker.state == CircuitState.CLOSED
    
    def test_half_open_to_open_on_failure(self, circuit_breaker):
        """Should transition from HALF_OPEN back to OPEN on failure."""
        # Force HALF_OPEN state
        circuit_breaker._state = CircuitState.HALF_OPEN
        
        circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
    
    def test_context_manager_success(self, circuit_breaker):
        """Should execute function successfully when CLOSED."""
        with circuit_breaker:
            result = "success"
        
        assert result == "success"
        assert circuit_breaker._stats.successful_calls == 1
    
    def test_context_manager_failure(self, circuit_breaker):
        """Should record failure when function raises exception."""
        with pytest.raises(ValueError):
            with circuit_breaker:
                raise ValueError("test error")
        
        assert circuit_breaker._stats.consecutive_failures == 1
    
    def test_context_manager_blocks_when_open(self, circuit_breaker):
        """Should raise CircuitBreakerOpen when OPEN."""
        # Force OPEN state
        for _ in range(5):
            circuit_breaker.record_failure()
        
        with pytest.raises(CircuitBreakerOpen):
            with circuit_breaker:
                pass
    
    def test_get_stats(self, circuit_breaker):
        """Should return correct statistics."""
        circuit_breaker.record_success()
        circuit_breaker.record_failure()
        
        stats = circuit_breaker.get_stats()
        
        assert stats["name"] == "test_breaker"
        assert stats["state"] == "closed"
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 1
        assert stats["failed_calls"] == 1
    
    def test_reset(self, circuit_breaker):
        """Should reset circuit breaker to initial state."""
        for _ in range(5):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        circuit_breaker.reset()
        
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._stats.consecutive_failures == 0


class TestSlidingWindowCircuitBreaker:
    """Tests for the SlidingWindowCircuitBreaker (failure rate threshold)."""
    
    @pytest.fixture
    def sliding_breaker(self):
        """Create a sliding window circuit breaker with test configuration."""
        return SlidingWindowCircuitBreaker(
            "test_sliding",
            config=SlidingWindowConfig(
                window_size=60.0,
                min_calls=5,
                failure_rate_threshold=0.5,
                consecutive_failures=5,
                timeout=30.0,
                success_threshold=2
            )
        )
    
    def test_initial_state_is_closed(self, sliding_breaker):
        """Sliding window breaker should start in CLOSED state."""
        assert sliding_breaker.state == CircuitState.CLOSED
    
    def test_opens_on_consecutive_failures(self, sliding_breaker):
        """Should OPEN after consecutive failures reach threshold."""
        for _ in range(5):
            sliding_breaker.record_failure()
        
        assert sliding_breaker.state == CircuitState.OPEN
    
    def test_stays_closed_below_threshold(self, sliding_breaker):
        """Should stay CLOSED when failure rate is below threshold."""
        # 3 failures, 7 successes = 30% failure rate
        for _ in range(3):
            sliding_breaker.record_failure()
        for _ in range(7):
            sliding_breaker.record_success()
        
        assert sliding_breaker.state == CircuitState.CLOSED
    
    def test_respects_min_calls(self, sliding_breaker):
        """Should not open before minimum calls are made."""
        # Only 4 failures, below min_calls=5
        for _ in range(4):
            sliding_breaker.record_failure()
        
        assert sliding_breaker.state == CircuitState.CLOSED
    
    def test_get_stats(self, sliding_breaker):
        """Should return correct statistics."""
        sliding_breaker.record_success()
        sliding_breaker.record_failure()
        
        stats = sliding_breaker.get_stats()
        
        assert stats["name"] == "test_sliding"
        assert stats["state"] == "closed"
        assert stats["window_calls"] == 2
        assert stats["window_failures"] == 1
    
    def test_reset(self, sliding_breaker):
        """Should reset sliding window breaker to initial state."""
        for _ in range(5):
            sliding_breaker.record_failure()
        
        assert sliding_breaker.state == CircuitState.OPEN
        
        sliding_breaker.reset()
        
        assert sliding_breaker.state == CircuitState.CLOSED
        assert sliding_breaker._consecutive_failures == 0


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with data sources."""
    
    @pytest.fixture
    def mock_data_source(self):
        """Create a mock data source with circuit breaker."""
        class MockDataSource:
            def __init__(self):
                self.breaker = CircuitBreaker(
                    "mock_source",
                    config=CircuitBreakerConfig(
                        failure_threshold=3,
                        success_threshold=2,
                        timeout=5.0,
                        half_open_max_calls=3
                    )
                )
                self.call_count = 0
            
            async def fetch(self, should_fail=False):
                self.call_count += 1
                if should_fail:
                    raise ConnectionError("Data source unavailable")
                return {"data": "success"}
        
        return MockDataSource()
    
    @pytest.mark.asyncio
    async def test_successful_fetch(self, mock_data_source):
        """Should successfully fetch data when circuit is closed."""
        with mock_data_source.breaker:
            result = await mock_data_source.fetch(should_fail=False)
        
        assert result == {"data": "success"}
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, mock_data_source):
        """Should open circuit after consecutive failures."""
        # Trigger 3 failures
        for _ in range(3):
            try:
                with mock_data_source.breaker:
                    await mock_data_source.fetch(should_fail=True)
            except ConnectionError:
                pass
        
        # Circuit should be OPEN
        assert mock_data_source.breaker.state == CircuitState.OPEN
        
        # Should raise CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            with mock_data_source.breaker:
                await mock_data_source.fetch(should_fail=False)
    
    @pytest.mark.asyncio
    async def test_circuit_recovers_after_timeout(self, mock_data_source):
        """Should recover to half-open after timeout."""
        # Trigger 3 failures
        for _ in range(3):
            try:
                with mock_data_source.breaker:
                    await mock_data_source.fetch(should_fail=True)
            except ConnectionError:
                pass
        
        assert mock_data_source.breaker.state == CircuitState.OPEN
        
        # Simulate timeout
        mock_data_source.breaker._opened_at = time.time() - 6
        
        # Should transition to HALF_OPEN and allow request
        assert mock_data_source.breaker.state == CircuitState.HALF_OPEN
        
        # Successful request should close the circuit
        with mock_data_source.breaker:
            result = await mock_data_source.fetch(should_fail=False)
        
        # Need 2 successes to close (success_threshold=2)
        mock_data_source.breaker._stats.consecutive_successes = 1
        with mock_data_source.breaker:
            result = await mock_data_source.fetch(should_fail=False)
        
        assert mock_data_source.breaker.state == CircuitState.CLOSED


class TestCircuitBreakerEdgeCases:
    """Edge case tests for circuit breaker."""
    
    def test_boundary_failure_rate_below_threshold(self):
        """Should stay CLOSED at exactly 49.9% failure rate."""
        breaker = SlidingWindowCircuitBreaker(
            "test_boundary",
            config=SlidingWindowConfig(
                window_size=60.0,
                min_calls=10,
                failure_rate_threshold=0.5,
                consecutive_failures=100,  # High to avoid triggering
                timeout=30.0,
                success_threshold=2
            )
        )
        
        # 4 failures, 6 successes = 40% failure rate
        for _ in range(4):
            breaker.record_failure()
        for _ in range(6):
            breaker.record_success()
        
        assert breaker.state == CircuitState.CLOSED
    
    def test_boundary_failure_rate_at_threshold(self):
        """Should OPEN at exactly 50% failure rate when next failure occurs."""
        breaker = SlidingWindowCircuitBreaker(
            "test_boundary",
            config=SlidingWindowConfig(
                window_size=60.0,
                min_calls=10,
                failure_rate_threshold=0.5,
                consecutive_failures=100,
                timeout=30.0,
                success_threshold=2
            )
        )
        
        for _ in range(5):
            breaker.record_failure()
        for _ in range(5):
            breaker.record_success()
        
        stats = breaker.get_stats()
        assert stats["failure_rate"] == 0.5
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
    
    def test_concurrent_access(self):
        """Should handle concurrent access safely."""
        breaker = CircuitBreaker(
            "test_concurrent",
            config=CircuitBreakerConfig(
                failure_threshold=100,
                success_threshold=2,
                timeout=30.0,
                half_open_max_calls=3
            )
        )
        
        async def concurrent_operations():
            tasks = []
            for i in range(100):
                if i % 2 == 0:
                    tasks.append(asyncio.create_task(
                        asyncio.to_thread(breaker.record_failure)
                    ))
                else:
                    tasks.append(asyncio.create_task(
                        asyncio.to_thread(breaker.record_success)
                    ))
            await asyncio.gather(*tasks)
        
        asyncio.run(concurrent_operations())
        
        # Should have processed all calls
        stats = breaker.get_stats()
        assert stats["total_calls"] == 100
    
    def test_zero_timeout(self):
        """Should handle zero recovery timeout - immediately transitions to HALF_OPEN."""
        breaker = CircuitBreaker(
            "test_zero_timeout",
            config=CircuitBreakerConfig(
                failure_threshold=1,
                success_threshold=2,
                timeout=0.0,
                half_open_max_calls=3
            )
        )
        
        breaker.record_failure()
        assert breaker._state == CircuitState.OPEN
        assert breaker.state == CircuitState.HALF_OPEN
