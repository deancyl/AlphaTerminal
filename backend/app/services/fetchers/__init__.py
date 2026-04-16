"""
Data fetchers package for AlphaTerminal.

Provides unified interface for fetching market data from different sources.
Includes circuit breaker pattern for fault tolerance.
"""

from .base import BaseMarketFetcher
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitContext
from .fetcher_factory import FetcherFactory, get_market_fetcher, fetch_with_fallback

# Import and register fetchers
from .sina import SinaFetcher
from .tencent import TencentFetcher
from .eastmoney import EastmoneyFetcher

# Register all fetchers (Sina as default)
FetcherFactory.register("sina", SinaFetcher, as_default=True)
FetcherFactory.register("tencent", TencentFetcher)
FetcherFactory.register("eastmoney", EastmoneyFetcher)

__all__ = [
    # Base classes
    "BaseMarketFetcher",
    # Circuit breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitContext",
    # Factory
    "FetcherFactory",
    "get_market_fetcher",
    "fetch_with_fallback",
    # Fetchers
    "SinaFetcher",
    "TencentFetcher",
]