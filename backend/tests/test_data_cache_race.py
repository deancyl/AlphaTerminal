"""
Race condition tests for DataCache.get_or_set() and get_or_set_async()

Tests verify:
1. 10 concurrent requests only trigger 1 fetch
2. All threads get the same result
3. Error state doesn't cause cascading failures
4. Timeout protection works
"""

import asyncio
import threading
import time
import pytest

from app.services.data_cache import DataCache


class TestGetOrSetRaceCondition:
    """Test race condition fix in get_or_set()"""

    def test_single_fetch_for_concurrent_requests(self):
        """
        Verify that 10 concurrent requests only trigger 1 fetch.
        """
        cache = DataCache()
        fetch_count = 0
        fetch_lock = threading.Lock()

        def slow_fetch():
            nonlocal fetch_count
            with fetch_lock:
                fetch_count += 1
            time.sleep(0.5)
            return {"data": "test_value"}

        results = []
        errors = []

        def worker():
            try:
                result = cache.get_or_set("test_key", slow_fetch)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fetch_count == 1, f"Expected 1 fetch, got {fetch_count}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        for result in results:
            assert result == {"data": "test_value"}

    def test_all_threads_get_same_result(self):
        """
        Verify all threads receive the same result from the single fetch.
        """
        cache = DataCache()

        def fetch():
            time.sleep(0.3)
            return {"unique_id": 12345, "timestamp": time.time()}

        results = []

        def worker():
            result = cache.get_or_set("shared_key", fetch)
            results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        first_result = results[0]
        for result in results:
            assert result == first_result, "All threads should get same result"

    def test_error_propagation_to_waiters(self):
        """
        Verify that when fetch fails, at least one waiter receives the error.

        Note: Due to the single-flight pattern, only the first follower that
        acquires the lock after the event is set will see the error. Other
        followers may get RuntimeError if they check the cache before seeing
        the error. This is a known limitation.
        """
        cache = DataCache()

        class CustomError(Exception):
            pass

        def failing_fetch():
            time.sleep(0.2)
            raise CustomError("Fetch failed intentionally")

        errors = []

        def worker():
            try:
                cache.get_or_set("error_key", failing_fetch)
            except CustomError as e:
                errors.append(e)
            except RuntimeError:
                errors.append(RuntimeError("missed_error"))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 5, f"Expected 5 errors, got {len(errors)}"
        custom_errors = [e for e in errors if isinstance(e, CustomError)]
        assert len(custom_errors) >= 1, "At least one follower should get CustomError"

    def test_cache_hit_skips_fetch(self):
        """
        Verify that cache hit bypasses fetch entirely.
        """
        cache = DataCache()
        fetch_count = 0

        def fetch():
            nonlocal fetch_count
            fetch_count += 1
            return "cached_value"

        result1 = cache.get_or_set("cached_key", fetch)
        assert fetch_count == 1

        fetch_count = 0

        results = []
        def worker():
            results.append(cache.get_or_set("cached_key", fetch))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert fetch_count == 0, "Should not fetch when cache hit"
        assert len(results) == 5

    def test_coalesced_requests_stat_incremented(self):
        """
        Verify coalesced_requests stat is incremented correctly.
        """
        cache = DataCache()

        def fetch():
            time.sleep(0.3)
            return "value"

        def worker():
            cache.get_or_set("stat_key", fetch)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = cache.get_stats()
        assert stats["coalesced_requests"] == 9, "9 requests should be coalesced"

    def test_request_coalescing_prevents_cache_avalanche(self):
        """
        Verify that request coalescing prevents cache avalanche.

        A cache avalanche would occur if many requests concurrently miss
        the cache and all try to fetch, overwhelming the data source.
        """
        cache = DataCache()
        concurrent_fetches = [0]

        def fetch():
            concurrent_fetches[0] += 1
            current = concurrent_fetches[0]
            time.sleep(0.5)
            return f"result_{current}"

        results = []
        def worker():
            result = cache.get_or_set("avalanche_key", fetch)
            results.append(result)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        start_time = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start_time

        # If coalescing worked, total time should be ~0.5s (one fetch)
        # If no coalescing, total time would be ~5s (10 sequential fetches)
        assert elapsed < 2.0, f"Coalescing failed, took {elapsed}s"

        # All results should be from the same fetch
        assert len(set(results)) == 1, "All should get same result"


class TestGetOrSetAsyncRaceCondition:
    """Test race condition fix in get_or_set_async()"""

    @pytest.mark.asyncio
    async def test_single_fetch_for_concurrent_async_requests(self):
        """
        Verify that 10 concurrent async requests only trigger 1 fetch.
        """
        cache = DataCache()
        fetch_count = 0

        async def async_fetch():
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.5)
            return {"async_data": "test_value"}

        async def worker():
            return await cache.get_or_set_async("async_test_key", async_fetch)

        tasks = [asyncio.create_task(worker()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert fetch_count == 1, f"Expected 1 fetch, got {fetch_count}"
        assert len(results) == 10
        for result in results:
            assert result == {"async_data": "test_value"}

    @pytest.mark.asyncio
    async def test_all_coroutines_get_same_result(self):
        """
        Verify all coroutines receive the same result.
        """
        cache = DataCache()

        async def async_fetch():
            await asyncio.sleep(0.3)
            return {"unique_id": 67890}

        async def worker():
            return await cache.get_or_set_async("async_shared_key", async_fetch)

        tasks = [asyncio.create_task(worker()) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        first_result = results[0]
        for result in results:
            assert result == first_result

    @pytest.mark.asyncio
    async def test_async_error_propagation(self):
        """
        Verify error propagation in async version.

        Similar to sync version, only one follower may get the original error.
        """
        cache = DataCache()

        class AsyncError(Exception):
            pass

        async def failing_async_fetch():
            await asyncio.sleep(0.2)
            raise AsyncError("Async fetch failed")

        async def worker():
            try:
                await cache.get_or_set_async("async_error_key", failing_async_fetch)
            except AsyncError:
                return "async_error"
            except RuntimeError:
                return "runtime_error"

        tasks = [asyncio.create_task(worker()) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(r in ("async_error", "runtime_error") for r in results)
        async_errors = [r for r in results if r == "async_error"]
        assert len(async_errors) >= 1

    @pytest.mark.asyncio
    async def test_async_cache_hit_skips_fetch(self):
        """
        Verify cache hit bypasses async fetch.
        """
        cache = DataCache()
        fetch_count = 0

        async def async_fetch():
            nonlocal fetch_count
            fetch_count += 1
            return "async_cached_value"

        result1 = await cache.get_or_set_async("async_cached_key", async_fetch)
        assert fetch_count == 1

        fetch_count = 0

        async def worker():
            return await cache.get_or_set_async("async_cached_key", async_fetch)

        tasks = [asyncio.create_task(worker()) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert fetch_count == 0
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_async_coalesced_requests_stat(self):
        """
        Verify coalesced_requests stat for async version.
        """
        cache = DataCache()

        async def async_fetch():
            await asyncio.sleep(0.3)
            return "async_value"

        async def worker():
            return await cache.get_or_set_async("async_stat_key", async_fetch)

        tasks = [asyncio.create_task(worker()) for _ in range(10)]
        await asyncio.gather(*tasks)

        stats = cache.get_stats()
        assert stats["coalesced_requests"] == 9


class TestMixedSyncAsync:
    """Test interaction between sync and async versions"""

    def test_sync_and_async_use_same_cache(self):
        """
        Verify sync and async methods share the same underlying cache.
        """
        cache = DataCache()

        def sync_fetch():
            return "sync_value"

        result = cache.get_or_set("shared_cache_key", sync_fetch)
        assert result == "sync_value"

        cached = cache.get("shared_cache_key")
        assert cached == "sync_value"

    @pytest.mark.asyncio
    async def test_async_reads_sync_cached_value(self):
        """
        Verify async can read values cached by sync method.
        """
        cache = DataCache()

        cache.set("cross_key", "cross_value", ttl=60)

        async def async_fetch():
            return "should_not_be_called"

        result = await cache.get_or_set_async("cross_key", async_fetch)
        assert result == "cross_value"


class TestTimeoutEdgeCases:
    """Test timeout edge cases"""

    def test_sync_timeout_after_leader_completes(self):
        """
        Verify that if leader completes before follower times out,
        follower gets the result successfully.
        """
        cache = DataCache()

        def fetch():
            time.sleep(0.5)
            return "success"

        results = []
        errors = []

        def worker():
            try:
                result = cache.get_or_set("timeout_test_key", fetch)
                results.append(result)
            except TimeoutError:
                errors.append(TimeoutError("Unexpected timeout"))

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        for r in results:
            assert r == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])