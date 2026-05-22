"""Unit tests for Singleflight utility."""

import asyncio
import pytest

from app.utils.singleflight import Singleflight, get_singleflight


class TestSingleflight:
    """Test suite for Singleflight class."""

    @pytest.mark.asyncio
    async def test_single_request_returns_result(self):
        """Single request should return the result."""
        sf = Singleflight()
        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return {"data": "value"}

        result = await sf.do("test_key", fetch)

        assert result == {"data": "value"}
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_requests_share_same_result(self):
        """Concurrent requests with same key should share result."""
        sf = Singleflight()
        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"data": "value"}

        async def make_request():
            return await sf.do("test_key", fetch)

        results = await asyncio.gather(*[make_request() for _ in range(10)])

        assert all(r == {"data": "value"} for r in results)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_error_is_propagated_to_all_waiters(self):
        """Error in fn should be propagated to all waiters."""
        sf = Singleflight()
        call_count = 0

        async def failing_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            raise ValueError("API error")

        async def make_request():
            try:
                await sf.do("test_key", failing_fetch)
                return None
            except ValueError as e:
                return str(e)

        errors = await asyncio.gather(*[make_request() for _ in range(5)])

        assert all(e == "API error" for e in errors)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_cancelled_waiter_doesnt_affect_others(self):
        """Cancelled waiter should not affect other waiters."""
        sf = Singleflight()
        call_count = 0
        results = []

        async def slow_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.2)
            return {"data": "value"}

        async def waiter(index: int):
            result = await sf.do("test_key", slow_fetch)
            results.append((index, result))

        async def cancelled_waiter():
            try:
                await asyncio.wait_for(sf.do("test_key", slow_fetch), timeout=0.05)
            except asyncio.TimeoutError:
                pass

        await asyncio.gather(
            waiter(1), waiter(2), cancelled_waiter(), waiter(3), return_exceptions=True
        )

        await asyncio.sleep(0.3)

        assert call_count == 1
        assert len(results) == 3
        assert all(r[1] == {"data": "value"} for r in results)

    @pytest.mark.asyncio
    async def test_key_cleanup_after_completion(self):
        """Key should be removed from _in_flight after completion."""
        sf = Singleflight()

        async def fetch():
            return "result"

        await sf.do("test_key", fetch)

        assert "test_key" not in sf._in_flight

    @pytest.mark.asyncio
    async def test_key_cleanup_after_error(self):
        """Key should be removed from _in_flight after error."""
        sf = Singleflight()

        async def failing_fetch():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await sf.do("test_key", failing_fetch)

        assert "test_key" not in sf._in_flight

    @pytest.mark.asyncio
    async def test_different_keys_execute_separately(self):
        """Different keys should execute separately."""
        sf = Singleflight()
        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return call_count

        results = await asyncio.gather(
            sf.do("key1", fetch),
            sf.do("key2", fetch),
            sf.do("key3", fetch),
        )

        assert results == [1, 2, 3]
        assert call_count == 3

    def test_make_key_consistency(self):
        """make_key should return consistent hash for same arguments."""
        key1 = Singleflight.make_key("gdp", limit=10)
        key2 = Singleflight.make_key("gdp", limit=10)

        assert key1 == key2

    def test_make_key_different_arguments(self):
        """make_key should return different hash for different arguments."""
        key1 = Singleflight.make_key("gdp", limit=10)
        key2 = Singleflight.make_key("gdp", limit=20)
        key3 = Singleflight.make_key("cpi", limit=10)

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_get_singleflight_returns_global_instance(self):
        """get_singleflight should return the global instance."""
        sf1 = get_singleflight()
        sf2 = get_singleflight()

        assert sf1 is sf2

    @pytest.mark.asyncio
    async def test_sequential_requests_execute_separately(self):
        """Sequential requests should execute separately (no dedup)."""
        sf = Singleflight()
        call_count = 0

        async def fetch():
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = await sf.do("test_key", fetch)
        result2 = await sf.do("test_key", fetch)

        assert result1 == 1
        assert result2 == 2
        assert call_count == 2
