"""
Data fetchers package for AlphaTerminal.

Provides unified interface for fetching market data from different sources.
Includes circuit breaker pattern for fault tolerance.
"""

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpen, CircuitContext
from .fetcher_factory import (
    FetcherFactory,
    get_market_fetcher,
    fetch_with_fallback,
    fetch_by_priority,
    get_quote_by_priority,
    get_kline_by_priority,
)

# Import and register fetchers
from .sina import SinaFetcher
from .tencent import TencentFetcher
from .eastmoney import EastmoneyFetcher
from .akshare_fetcher import AkShareFetcher

# Register all fetchers (Sina as default for realtime, AkShare for history)
FetcherFactory.register("sina", SinaFetcher, as_default=True)
FetcherFactory.register("tencent", TencentFetcher)
FetcherFactory.register("eastmoney", EastmoneyFetcher)
FetcherFactory.register("akshare", AkShareFetcher)

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
    "fetch_by_priority",
    "get_quote_by_priority",
    "get_kline_by_priority",
    # Fetchers
    "SinaFetcher",
    "TencentFetcher",
    "EastmoneyFetcher",
    "AkShareFetcher",
]