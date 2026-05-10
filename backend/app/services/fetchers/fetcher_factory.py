"""
Fetcher Factory — Unified interface for market data sources

Provides:
- FetcherFactory: registry of fetchers with fallback support
- fetch_with_fallback: try primary → fallback1 → fallback2 on failure
- get_market_fetcher: get fetcher by name
"""
import logging
from typing import Optional, Dict, Any, Callable, Awaitable

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitContext

logger = logging.getLogger(__name__)

# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """Get or create circuit breaker for a fetcher"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config or CircuitBreakerConfig())
    return _circuit_breakers[name]


class FetcherFactory:
    """
    Factory for creating and managing market data fetchers.
    
    Usage:
        FetcherFactory.register("sina", SinaFetcher, as_default=True)
        FetcherFactory.register("tencent", TencentFetcher)
        
        factory = FetcherFactory()
        fetcher = factory.get_fetcher("sina")
        
        # With fallback:
        result = await fetch_with_fallback(
            lambda: fetcher.get_quote("sh000001"),
            fallbacks=["tencent", "eastmoney"]
        )
    """

    _fetchers: Dict[str, type] = {}
    _default_fetcher: Optional[str] = None

    @classmethod
    def register(cls, name: str, fetcher_cls: type, as_default: bool = False):
        """Register a fetcher class"""
        if not issubclass(fetcher_cls, BaseMarketFetcher):
            raise TypeError(f"{fetcher_cls} must inherit from BaseMarketFetcher")
        cls._fetchers[name] = fetcher_cls
        if as_default:
            cls._default_fetcher = name
        logger.info(f"[FetcherFactory] Registered fetcher: {name} (default={as_default})")

    @classmethod
    def get_fetcher(cls, name: Optional[str] = None) -> BaseMarketFetcher:
        """Get an instance of a named fetcher"""
        name = name or cls._default_fetcher
        if not name:
            raise ValueError("No fetcher name provided and no default set")
        if name not in cls._fetchers:
            raise ValueError(f"Unknown fetcher: {name}. Available: {list(cls._fetchers.keys())}")
        return cls._fetchers[name]()

    @classmethod
    def list_fetchers(cls) -> list:
        """List all registered fetcher names"""
        return list(cls._fetchers.keys())

    @classmethod
    def get_default(cls) -> Optional[str]:
        return cls._default_fetcher

    @classmethod
    def circuit_status(cls) -> Dict[str, dict]:
        """Get status of all circuit breakers"""
        return {name: cb.get_stats() for name, cb in _circuit_breakers.items()}

    @classmethod
    def reset_circuit(cls, name: str):
        """Manually reset a circuit breaker to CLOSED state"""
        if name in _circuit_breakers:
            cb = _circuit_breakers[name]
            cb._state = cb._state.__class__.CLOSED
            cb._failure_count = 0
            cb._success_count = 0
            logger.info(f"[FetcherFactory] Circuit breaker reset: {name}")


def get_market_fetcher(name: Optional[str] = None) -> BaseMarketFetcher:
    """Convenience function: get a fetcher instance"""
    return FetcherFactory.get_fetcher(name)


async def fetch_with_fallback(
    fetch_fn: Callable[[], Awaitable[Any]],
    fallbacks: Optional[list] = None,
    source_name: str = "primary",
) -> Any:
    """
    Try fetch_fn; on failure, try fallback sources in order.
    
    Args:
        fetch_fn: Async function that returns data
        fallbacks: List of fallback fetcher names (strings) to try on failure
        source_name: Name for logging
    
    Returns:
        Data from the first successful source
    
    Raises:
        Last exception if all sources fail
    """
    sources = [source_name] + (fallbacks or [])
    last_error = None

    for i, src in enumerate(sources):
        cb = get_circuit_breaker(src)
        if not cb.is_available():
            logger.debug(f"[fetch_with_fallback] {src}: circuit open, skipping")
            continue

        try:
            with CircuitContext(cb, src) as ctx:
                result = await fetch_fn()
                return result
        except CircuitBreakerOpen:
            logger.debug(f"[fetch_with_fallback] {src}: circuit open (pre-check)")
            continue
        except Exception as e:
            last_error = e
            logger.warning(f"[fetch_with_fallback] {src} failed: {e}")
            continue

    # All sources failed
    if last_error:
        raise last_error
    raise RuntimeError(f"All fallback sources failed for {source_name}")
