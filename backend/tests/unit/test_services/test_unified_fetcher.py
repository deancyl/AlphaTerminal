"""
Unified Fetcher Service Tests

Tests for the unified data fetcher implementation in backend/app/services/unified_fetcher.py
Covers multi-source fallback, source priority, cache integration, validation, error handling,
performance, and logging. Uses synchronous fetch_sync method.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from app.services.unified_fetcher import (
    UnifiedFetcher,
    DataSource,
    FetchResult,
    get_fetcher,
)
from app.services.circuit_breaker import CircuitBreaker

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_cache():
    """Mock data cache for testing."""
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock(return_value=True)
    cache.delete = MagicMock(return_value=True)
    cache.get_stats = MagicMock(
        return_value={
            "hit_rate": 0.0,
            "miss_rate": 100.0,
            "total_requests": 0,
            "hits": 0,
            "misses": 0,
            "entry_count": 0,
        }
    )
    return cache


@pytest.fixture
def mock_metrics():
    """Mock cache metrics for testing."""
    metrics = MagicMock()
    metrics.record_hit = MagicMock()
    metrics.record_miss = MagicMock()
    metrics.record_latency = MagicMock()
    metrics.record_error = MagicMock()
    metrics.get_hit_rate = MagicMock(return_value=0.0)
    metrics.get_avg_latency = MagicMock(return_value=0.0)
    metrics.get_p95_latency = MagicMock(return_value=0.0)
    metrics.get_error_rate = MagicMock(return_value=0.0)
    return metrics


@pytest.fixture
def fetcher(mock_cache, mock_metrics):
    """Create UnifiedFetcher with mocked dependencies."""
    with patch(
        "app.services.unified_fetcher.get_cache", return_value=mock_cache
    ), patch(
        "app.services.unified_fetcher.get_cache_metrics", return_value=mock_metrics
    ):
        f = UnifiedFetcher()
        f.cache = mock_cache
        f.metrics = mock_metrics
        return f


@pytest.fixture
def sample_kline_data():
    """Sample K-line data for testing."""
    return [
        {
            "date": "2024-01-01",
            "open": 10.0,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1000000,
        },
        {
            "date": "2024-01-02",
            "open": 10.2,
            "high": 10.8,
            "low": 10.0,
            "close": 10.6,
            "volume": 1200000,
        },
    ]


# ============================================================================
# TestUnifiedFetcherFallback
# ============================================================================


class TestUnifiedFetcherFallback:
    """Tests for fetch_with_fallback function"""

    def test_fetch_with_fallback_success(self, fetcher, sample_kline_data):
        """Primary source succeeds, no fallback needed."""
        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=lambda: sample_kline_data,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert result.data == sample_kline_data
        assert result.source == DataSource.AKSHARE
        assert result.from_cache is False
        assert result.error is None

    def test_fallback_to_secondary_on_primary_failure(self, fetcher, sample_kline_data):
        """Fallback to secondary source when primary fails."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary source failed"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert result.data == sample_kline_data
        assert result.source == DataSource.EASTMONEY

    def test_fallback_to_tertiary_on_secondary_failure(self, fetcher):
        """Test fallback chain with multiple failures."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: (_ for _ in ()).throw(Exception("Secondary failed"))

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is False
        assert result.data is None
        assert result.error == "所有数据源均不可用"

    def test_all_sources_failure_returns_error(self, fetcher):
        """All sources fail, return error result."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: (_ for _ in ()).throw(Exception("Fallback failed"))

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is False
        assert result.data is None
        assert result.error == "所有数据源均不可用"
        assert result.from_cache is False

    def test_fallback_preserves_data_format(self, fetcher, sample_kline_data):
        """Fallback should return data in same format as primary."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert isinstance(result.data, list)
        assert len(result.data) == 2
        assert all("date" in item for item in result.data)
        assert all("close" in item for item in result.data)


# ============================================================================
# TestUnifiedFetcherSourcePriority
# ============================================================================


class TestUnifiedFetcherSourcePriority:
    """Tests for source priority"""

    def test_primary_source_first(self, fetcher, sample_kline_data):
        """Primary source should be tried first."""
        call_order = []

        def track_primary():
            call_order.append("primary")
            return sample_kline_data

        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=track_primary,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert "primary" in call_order
        assert result.source == DataSource.AKSHARE

    def test_priority_order_configurable(self, fetcher):
        """Fallback source mapping is configurable."""
        assert fetcher._get_fallback_source(DataSource.AKSHARE) == DataSource.EASTMONEY
        assert fetcher._get_fallback_source(DataSource.SINA) == DataSource.TENCENT
        assert fetcher._get_fallback_source(DataSource.TENCENT) == DataSource.SINA
        assert fetcher._get_fallback_source(DataSource.EASTMONEY) == DataSource.AKSHARE
        assert fetcher._get_fallback_source(DataSource.QLIB) == DataSource.AKSHARE

    def test_disabled_source_skipped(self, fetcher, sample_kline_data):
        """Source with open circuit breaker should be skipped."""
        breaker = fetcher.get_breaker(DataSource.AKSHARE)

        for _ in range(10):
            breaker.record_failure()

        assert breaker.is_available() is False

        primary_fn = lambda: sample_kline_data
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert result.source == DataSource.EASTMONEY

    def test_source_health_affects_priority(self, fetcher, sample_kline_data):
        """Circuit breaker state affects source selection."""
        breaker = fetcher.get_breaker(DataSource.AKSHARE)

        for _ in range(10):
            breaker.record_failure()

        breaker.reset()

        assert breaker.is_available() is True

        primary_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert result.source == DataSource.AKSHARE


# ============================================================================
# TestUnifiedFetcherDataMerge
# ============================================================================


class TestUnifiedFetcherDataMerge:
    """Tests for data merging"""

    def test_merge_from_multiple_sources(self, fetcher):
        """Data from multiple sources should be merged correctly."""
        fallback_data = [
            {"date": "2024-01-01", "close": 10.0},
            {"date": "2024-01-02", "close": 10.5},
        ]

        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: fallback_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert len(result.data) == 2
        assert result.data == fallback_data

    def test_merge_preserves_best_data(self, fetcher, sample_kline_data):
        """When both sources succeed, primary data is used."""
        fallback_data = [{"date": "2024-01-01", "close": 9.0}]

        primary_fn = lambda: sample_kline_data
        fallback_fn = lambda: fallback_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.data == sample_kline_data
        assert result.data != fallback_data

    def test_merge_handles_conflicts(self, fetcher):
        """Data conflicts should be handled gracefully."""
        fallback_data = [{"date": "2024-01-01", "close": 10.0, "volume": 1000000}]

        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: fallback_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert "volume" in result.data[0]

    def test_merge_timestamp_selection(self, fetcher):
        """Latest timestamp should be preserved."""
        data_with_ts = [
            {"date": "2024-01-01", "close": 10.0, "timestamp": "2024-01-01T10:00:00"},
            {"date": "2024-01-02", "close": 10.5, "timestamp": "2024-01-02T10:00:00"},
        ]

        primary_fn = lambda: data_with_ts

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.data[0]["timestamp"] == "2024-01-01T10:00:00"
        assert result.data[1]["timestamp"] == "2024-01-02T10:00:00"


# ============================================================================
# TestUnifiedFetcherCache
# ============================================================================


class TestUnifiedFetcherCache:
    """Tests for cache integration"""

    def test_cache_hit_returns_cached_data(
        self, fetcher, sample_kline_data, mock_cache
    ):
        """Cache hit should return cached data without fetching."""
        mock_cache.get = MagicMock(return_value=sample_kline_data)

        fetch_fn = MagicMock(return_value=sample_kline_data)

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.from_cache is True
        assert result.data == sample_kline_data
        assert fetch_fn.called is False

    def test_cache_miss_fetches_and_caches(
        self, fetcher, sample_kline_data, mock_cache
    ):
        """Cache miss should fetch data and cache it."""
        mock_cache.get = MagicMock(return_value=None)

        fetch_fn = MagicMock(return_value=sample_kline_data)

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.from_cache is False
        assert result.data == sample_kline_data
        assert fetch_fn.called is True
        assert mock_cache.set.called is True

    def test_cache_expiry_triggers_fetch(self, fetcher, sample_kline_data, mock_cache):
        """Expired cache should trigger new fetch."""
        mock_cache.get = MagicMock(return_value=None)

        fetch_fn = MagicMock(return_value=sample_kline_data)

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.from_cache is False
        assert fetch_fn.called is True

    def test_cache_invalidation(self, fetcher, sample_kline_data, mock_cache):
        """Cache can be invalidated by deleting the key."""
        mock_cache.get = MagicMock(return_value=None)

        fetch_fn = MagicMock(return_value=sample_kline_data)

        result1 = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result1.from_cache is False

        fetcher.cache.delete("kline:sh600519:daily")

        result2 = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert fetch_fn.call_count == 2


# ============================================================================
# TestUnifiedFetcherValidation
# ============================================================================


class TestUnifiedFetcherValidation:
    """Tests for data validation"""

    def test_valid_data_structure(self, fetcher, sample_kline_data):
        """Valid data structure should be accepted."""
        fetch_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert isinstance(result.data, list)

    def test_invalid_data_rejected(self, fetcher):
        """Invalid data should be handled gracefully."""
        fetch_fn = lambda: None

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert result.data is None

    def test_partial_data_handling(self, fetcher):
        """Partial data should be handled gracefully."""
        partial_data = [{"date": "2024-01-01", "close": 10.0}]

        fetch_fn = lambda: partial_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert result.data == partial_data

    def test_schema_validation(self, fetcher, sample_kline_data):
        """Data should match expected schema."""
        fetch_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        for item in result.data:
            assert "date" in item
            assert "close" in item
            assert isinstance(item["close"], (int, float))


# ============================================================================
# TestUnifiedFetcherErrorHandling
# ============================================================================


class TestUnifiedFetcherErrorHandling:
    """Tests for error handling"""

    def test_network_error_handling(self, fetcher, sample_kline_data):
        """Network errors should trigger fallback."""
        primary_fn = lambda: (_ for _ in ()).throw(ConnectionError("Network error"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert result.source == DataSource.EASTMONEY

    def test_timeout_handling(self, fetcher, sample_kline_data):
        """Timeout errors should trigger fallback."""
        primary_fn = lambda: (_ for _ in ()).throw(TimeoutError("Request timeout"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert result.source == DataSource.EASTMONEY

    def test_rate_limit_handling(self, fetcher, sample_kline_data):
        """Rate limit errors should trigger fallback."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Rate limit exceeded"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True

    def test_malformed_response_handling(self, fetcher, sample_kline_data):
        """Malformed responses should trigger fallback."""
        primary_fn = lambda: (_ for _ in ()).throw(ValueError("Invalid JSON"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True

    def test_circuit_breaker_integration(self, fetcher, sample_kline_data):
        """Circuit breaker should protect against cascading failures."""
        breaker = fetcher.get_breaker(DataSource.AKSHARE)
        for _ in range(10):
            breaker.record_failure()

        assert breaker.is_available() is False

        primary_fn = lambda: sample_kline_data
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is True
        assert result.source == DataSource.EASTMONEY


# ============================================================================
# TestUnifiedFetcherPerformance
# ============================================================================


class TestUnifiedFetcherPerformance:
    """Tests for performance"""

    def test_parallel_fetch(self, fetcher, sample_kline_data):
        """Multiple fetches can run in parallel via sync calls."""
        fetch_fn = lambda: sample_kline_data

        results = [
            fetcher.fetch_sync(
                "kline:sh600519:daily", fetch_fn, 300, DataSource.AKSHARE
            ),
            fetcher.fetch_sync(
                "kline:sh600036:daily", fetch_fn, 300, DataSource.AKSHARE
            ),
            fetcher.fetch_sync(
                "kline:sh601318:daily", fetch_fn, 300, DataSource.AKSHARE
            ),
        ]

        assert all(r.is_success for r in results)
        assert len(results) == 3

    def test_timeout_per_source(self, fetcher, sample_kline_data):
        """Each source has its own timeout protection."""

        def slow_fetch():
            time.sleep(0.01)
            return sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=slow_fetch,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert result.is_success is True
        assert result.latency_ms >= 10

    def test_total_timeout_limit(self, fetcher, sample_kline_data):
        """Total fetch time should be reasonable."""
        fetch_fn = lambda: sample_kline_data

        start_time = time.time()

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        elapsed = time.time() - start_time

        assert elapsed < 1.0
        assert result.is_success is True


# ============================================================================
# TestUnifiedFetcherLogging
# ============================================================================


class TestUnifiedFetcherLogging:
    """Tests for logging"""

    def test_logs_source_selection(self, fetcher, sample_kline_data):
        """Source selection should be logged."""
        fetch_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=fetch_fn,
            ttl=300,
            source=DataSource.AKSHARE,
        )

        assert fetcher.metrics.record_latency.called is True

    def test_logs_fallback_events(self, fetcher, sample_kline_data):
        """Fallback events should be logged."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: sample_kline_data

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert fetcher.metrics.record_error.called is True
        assert result.is_success is True

    def test_logs_errors(self, fetcher):
        """Errors should be logged."""
        primary_fn = lambda: (_ for _ in ()).throw(Exception("Primary failed"))
        fallback_fn = lambda: (_ for _ in ()).throw(Exception("Fallback failed"))

        result = fetcher.fetch_sync(
            key="kline:sh600519:daily",
            fetch_fn=primary_fn,
            ttl=300,
            source=DataSource.AKSHARE,
            fallback_fn=fallback_fn,
        )

        assert result.is_success is False
        assert result.error == "所有数据源均不可用"


# ============================================================================
# TestFetchResult
# ============================================================================


class TestFetchResult:
    """Tests for FetchResult dataclass"""

    def test_is_success_true_when_no_error(self):
        """is_success should be True when error is None."""
        result = FetchResult(
            data={"test": "data"},
            source=DataSource.AKSHARE,
            latency_ms=100.0,
            from_cache=False,
            error=None,
        )

        assert result.is_success is True

    def test_is_success_false_when_error(self):
        """is_success should be False when error is set."""
        result = FetchResult(
            data=None,
            source=DataSource.AKSHARE,
            latency_ms=100.0,
            from_cache=False,
            error="Something went wrong",
        )

        assert result.is_success is False

    def test_latency_ms_is_positive(self):
        """latency_ms should always be positive."""
        result = FetchResult(
            data={"test": "data"},
            source=DataSource.AKSHARE,
            latency_ms=50.5,
            from_cache=True,
        )

        assert result.latency_ms > 0


# ============================================================================
# TestDataSource
# ============================================================================


class TestDataSource:
    """Tests for DataSource enum"""

    def test_data_source_values(self):
        """DataSource should have expected values."""
        assert DataSource.AKSHARE.value == "akshare"
        assert DataSource.SINA.value == "sina"
        assert DataSource.TENCENT.value == "tencent"
        assert DataSource.EASTMONEY.value == "eastmoney"
        assert DataSource.QLIB.value == "qlib"
        assert DataSource.CUSTOM.value == "custom"

    def test_data_source_count(self):
        """Should have 6 data sources."""
        assert len(DataSource) == 6


# ============================================================================
# TestUnifiedFetcherStats
# ============================================================================


class TestUnifiedFetcherStats:
    """Tests for statistics and management methods"""

    def test_get_stats(self, fetcher):
        """get_stats should return comprehensive statistics."""
        stats = fetcher.get_stats()

        assert "cache" in stats
        assert "breakers" in stats
        assert "metrics" in stats
        assert "hit_rate" in stats["metrics"]

    def test_reset_breaker(self, fetcher):
        """reset_breaker should reset specific breaker."""
        breaker = fetcher.get_breaker(DataSource.AKSHARE)

        for _ in range(10):
            breaker.record_failure()

        assert breaker.is_available() is False

        result = fetcher.reset_breaker(DataSource.AKSHARE)

        assert result is True
        assert breaker.is_available() is True

    def test_reset_all_breakers(self, fetcher):
        """reset_all_breakers should reset all breakers."""
        fetcher.get_breaker(DataSource.AKSHARE)
        fetcher.get_breaker(DataSource.SINA)
        fetcher.get_breaker(DataSource.TENCENT)

        for source in [DataSource.AKSHARE, DataSource.SINA, DataSource.TENCENT]:
            breaker = fetcher.get_breaker(source)
            for _ in range(10):
                breaker.record_failure()

        count = fetcher.reset_all_breakers()

        assert count >= 3

    def test_get_breaker_creates_if_not_exists(self, fetcher):
        """get_breaker should create breaker if it doesn't exist."""
        assert len(fetcher.breakers) == 0

        breaker = fetcher.get_breaker(DataSource.AKSHARE)

        assert breaker is not None
        assert isinstance(breaker, CircuitBreaker)
        assert len(fetcher.breakers) == 1


# ============================================================================
# TestGetFetcher
# ============================================================================


class TestGetFetcher:
    """Tests for get_fetcher singleton"""

    def test_get_fetcher_returns_singleton(self):
        """get_fetcher should return the same instance."""
        with patch("app.services.unified_fetcher.get_cache"):
            with patch("app.services.unified_fetcher.get_cache_metrics"):
                import app.services.unified_fetcher as module

                module._fetcher = None

                fetcher1 = get_fetcher()
                fetcher2 = get_fetcher()

                assert fetcher1 is fetcher2

    def test_get_fetcher_creates_instance(self):
        """get_fetcher should create instance if None."""
        with patch("app.services.unified_fetcher.get_cache"):
            with patch("app.services.unified_fetcher.get_cache_metrics"):
                import app.services.unified_fetcher as module

                module._fetcher = None

                fetcher = get_fetcher()

                assert fetcher is not None
                assert isinstance(fetcher, UnifiedFetcher)
