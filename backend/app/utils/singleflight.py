"""Production-grade Singleflight utility for request deduplication.

Prevents cache stampede when multiple concurrent requests hit the same slow endpoint.
Concurrent callers with the same key share a single future; the result (or error)
is propagated to all waiters.
"""

import asyncio
import hashlib
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class Singleflight:
    """Production-grade singleflight for FastAPI.

    Deduplicates concurrent identical async calls. Concurrent callers with the same
    key share a single future; the result (or error) is propagated to all waiters.

    Example:
        >>> sf = Singleflight()
        >>> async def fetch_data():
        ...     # Expensive operation (e.g., akshare API call)
        ...     return await expensive_api_call()
        ...
        >>> # Multiple concurrent calls will share the same result
        >>> result = await sf.do("cache_key", fetch_data)
    """

    def __init__(self):
        """Initialize the singleflight with an empty in-flight dict."""
        self._in_flight: dict[str, asyncio.Future] = {}

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """Generate unique key from arguments.

        Args:
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            SHA256 hash of the arguments

        Example:
            >>> key = Singleflight.make_key("gdp", limit=10)
            >>> # Returns consistent hash for same arguments
        """
        data = str(args) + str(sorted(kwargs.items()))
        return hashlib.sha256(data.encode()).hexdigest()

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute fn exactly once, others share result.

        Args:
            key: Deduplication key. Callers with the same key share the result.
            fn: Async callable to execute. Will only be called once per key.

        Returns:
            Result of fn

        Raises:
            Any exception raised by fn is propagated to all waiters.

        Example:
            >>> sf = Singleflight()
            >>> async def slow_api():
            ...     await asyncio.sleep(1)
            ...     return {"data": "value"}
            ...
            >>> # First caller triggers execution
            >>> result1 = await sf.do("api_key", slow_api)
            >>> # Concurrent caller shares result (no second API call)
            >>> result2 = await sf.do("api_key", slow_api)
            >>> assert result1 is result2
        """
        if key in self._in_flight:
            # Shield so cancelled follower doesn't poison shared Future
            return await asyncio.shield(self._in_flight[key])

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        # Prevent "Future exception was never retrieved"
        future.add_done_callback(
            lambda f: f.exception() if f.done() and not f.cancelled() else None
        )
        self._in_flight[key] = future

        try:
            result = await fn()
            future.set_result(result)
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            self._in_flight.pop(key, None)


# Global instance for convenience
_singleflight = Singleflight()


def get_singleflight() -> Singleflight:
    """Get the global singleflight instance.

    Returns:
        The global Singleflight instance

    Example:
        >>> sf = get_singleflight()
        >>> result = await sf.do("key", expensive_operation)
    """
    return _singleflight
