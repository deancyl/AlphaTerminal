"""
Fetcher Factory — Unified interface for market data sources

Provides:
- FetcherFactory: registry of fetchers with fallback support
- fetch_with_fallback: try primary → fallback1 → fallback2 on failure
- fetch_by_priority: 根据数据类型自动选择优先级路由
- get_market_fetcher: get fetcher by name
"""
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, List

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitContext
from app.config.fetcher_priority import get_fetcher_priority, FetcherPriority

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


async def fetch_by_priority(
    data_type: str,
    fetch_fn_factory: Callable[[str], Callable[[], Awaitable[Any]]],
    priority: Optional[FetcherPriority] = None,
) -> Any:
    """
    根据数据类型优先级自动选择数据源并尝试获取数据。
    
    Args:
        data_type: 数据类型 (history, realtime, fund_nav, futures, hk_stocks, us_stocks)
        fetch_fn_factory: 工厂函数，接收数据源名称，返回对应的异步获取函数
        priority: 可选的优先级配置，默认使用全局配置
    
    Returns:
        从第一个成功的数据源获取的数据
    
    Raises:
        最后一个异常，如果所有数据源都失败
    
    Example:
        result = await fetch_by_priority(
            "history",
            lambda src: FetcherFactory.get_fetcher(src).get_kline("sh600519", "day")
        )
    """
    priority = priority or get_fetcher_priority()
    sources = priority.get_sources(data_type)
    
    last_error = None
    successful_source = None
    
    for src in sources:
        cb = get_circuit_breaker(src)
        if not cb.is_available():
            logger.debug(f"[fetch_by_priority] {src}: 熔断器开启，跳过")
            continue
        
        try:
            fetch_fn = fetch_fn_factory(src)
            with CircuitContext(cb, src) as ctx:
                result = await fetch_fn()
                successful_source = src
                logger.info(f"[fetch_by_priority] {data_type} 数据成功获取自 {src}")
                return result
        except CircuitBreakerOpen:
            logger.debug(f"[fetch_by_priority] {src}: 熔断器开启 (预检查)")
            continue
        except Exception as e:
            last_error = e
            logger.warning(f"[fetch_by_priority] {src} 失败: {e}，尝试下一个数据源")
            continue
    
    if last_error:
        logger.error(f"[fetch_by_priority] {data_type} 所有数据源均失败")
        raise last_error
    raise RuntimeError(f"[fetch_by_priority] {data_type} 所有数据源均不可用（熔断器开启）")


async def get_quote_by_priority(symbol: str, priority: Optional[FetcherPriority] = None) -> Optional[Dict]:
    """根据优先级获取实时行情"""
    return await fetch_by_priority(
        "realtime",
        lambda src: FetcherFactory.get_fetcher(src).get_quote(symbol),
        priority
    )


async def get_kline_by_priority(symbol: str, period: str = "day", priority: Optional[FetcherPriority] = None) -> Optional[List[Dict]]:
    """根据优先级获取K线数据"""
    return await fetch_by_priority(
        "history",
        lambda src: FetcherFactory.get_fetcher(src).get_kline(symbol, period),
        priority
    )
