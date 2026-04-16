"""
数据源工厂 - FetcherFactory with Circuit Breaker
带熔断器模式的数据源管理器，支持故障自动切换
"""
import logging
from typing import Optional, Dict, Type, List, Callable
from .base import BaseMarketFetcher
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitContext

logger = logging.getLogger(__name__)


class FetcherFactory:
    """
    Factory for creating market data fetchers with circuit breaker support.
    
    Features:
    - Dynamic switching between data sources
    - Circuit breaker pattern for fault tolerance
    - Automatic fallback to backup sources
    - Health monitoring
    """
    
    _fetchers: Dict[str, Type[BaseMarketFetcher]] = {}
    _circuit_breakers: Dict[str, CircuitBreaker] = {}
    _current_fetcher: Optional[str] = None
    _proxy: Optional[str] = None
    _fallback_order: List[str] = []
    _default_config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=30.0
    )
    
    @classmethod
    def register(cls, name: str, fetcher_class: Type[BaseMarketFetcher], as_default: bool = False):
        """
        Register a new fetcher type.
        
        Args:
            name: Fetcher identifier
            fetcher_class: Fetcher class (must extend BaseMarketFetcher)
            as_default: Set as default fetcher if True
        """
        cls._fetchers[name] = fetcher_class
        cls._circuit_breakers[name] = CircuitBreaker(name, cls._default_config)
        
        if as_default or cls._current_fetcher is None:
            cls._current_fetcher = name
        
        if name not in cls._fallback_order:
            cls._fallback_order.append(name)
        
        logger.info(f"Registered fetcher: {name} (default: {as_default})")
    
    @classmethod
    def get_fetcher(cls, name: Optional[str] = None) -> Optional[BaseMarketFetcher]:
        """
        Get a fetcher instance by name.
        
        Args:
            name: Fetcher name. If None, returns current default fetcher.
            
        Returns:
            Fetcher instance or None if not found.
        """
        if name is None:
            name = cls._current_fetcher
        
        if name not in cls._fetchers:
            return None
        
        return cls._fetchers[name](proxy=cls._proxy)
    
    @classmethod
    def get_circuit_breaker(cls, name: Optional[str] = None) -> Optional[CircuitBreaker]:
        """Get circuit breaker for a fetcher."""
        if name is None:
            name = cls._current_fetcher
        return cls._circuit_breakers.get(name)
    
    @classmethod
    def get_circuit_breaker_stats(cls, name: Optional[str] = None) -> Optional[Dict]:
        """Get circuit breaker statistics."""
        cb = cls.get_circuit_breaker(name)
        return cb.get_stats() if cb else None
    
    @classmethod
    def set_current(cls, name: str) -> bool:
        """Set the current default fetcher."""
        if name not in cls._fetchers:
            return False
        cls._current_fetcher = name
        return True
    
    @classmethod
    def get_current_name(cls) -> Optional[str]:
        """Get the name of the current default fetcher."""
        return cls._current_fetcher
    
    @classmethod
    def list_fetchers(cls) -> List[str]:
        """List all available fetcher names."""
        return list(cls._fetchers.keys())
    
    @classmethod
    def get_fetcher_info(cls, name: str) -> Optional[Dict]:
        """Get information about a fetcher."""
        if name not in cls._fetchers:
            return None
        
        fetcher_class = cls._fetchers[name]
        cb = cls._circuit_breakers.get(name)
        
        return {
            "name": fetcher_class.name,
            "display_name": fetcher_class.display_name,
            "supported_features": fetcher_class.supported_features,
            "circuit_breaker": cb.get_stats() if cb else None,
        }
    
    @classmethod
    def set_proxy(cls, proxy: Optional[str]):
        """Set proxy for all fetchers."""
        cls._proxy = proxy
    
    @classmethod
    def get_proxy(cls) -> Optional[str]:
        """Get current proxy setting."""
        return cls._proxy
    
    @classmethod
    def get_all_stats(cls) -> Dict:
        """Get statistics for all fetchers."""
        stats = {}
        for name in cls._fetchers:
            cb = cls._circuit_breakers.get(name)
            if cb:
                stats[name] = cb.get_stats()
        return stats
    
    @classmethod
    def reset_circuit_breaker(cls, name: Optional[str] = None):
        """Reset circuit breaker for a fetcher or all."""
        if name:
            cb = cls._circuit_breakers.get(name)
            if cb:
                cb.reset()
        else:
            for cb in cls._circuit_breakers.values():
                cb.reset()


def get_market_fetcher(name: Optional[str] = None) -> Optional[BaseMarketFetcher]:
    """Get market fetcher instance."""
    return FetcherFactory.get_fetcher(name)


async def fetch_with_fallback(
    fetch_func: Callable,
    symbol: str,
    fallback_order: Optional[List[str]] = None
):
    """
    使用熔断器执行fetch，失败时自动切换数据源。
    
    Args:
        fetch_func: Async function to call (fetcher.get_quote, etc.)
        symbol: Symbol to fetch
        fallback_order: List of fetcher names to try in order
        
    Returns:
        Fetch result or None if all failed
        
    Raises:
        CircuitBreakerOpen: 如果所有数据源都熔断中
    """
    if fallback_order is None:
        fallback_order = FetcherFactory._fallback_order.copy()
    
    last_error = None
    
    for fetcher_name in fallback_order:
        cb = FetcherFactory.get_circuit_breaker(fetcher_name)
        if not cb:
            continue
        
        if not cb.is_available():
            logger.info(f"Circuit breaker OPEN for {fetcher_name}, trying next...")
            continue
        
        fetcher = FetcherFactory.get_fetcher(fetcher_name)
        if not fetcher:
            continue
        
        try:
            with CircuitContext(cb):
                result = await fetch_func(fetcher, symbol)
                cb.record_success()
                return result
        except CircuitBreakerOpen:
            raise
        except Exception as e:
            logger.warning(f"Fetcher {fetcher_name} failed: {e}")
            cb.record_failure()
            last_error = e
            continue
    
    if last_error:
        raise last_error
    return None