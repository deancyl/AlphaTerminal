"""
Data fetchers package for AlphaTerminal.

Provides unified interface for fetching market data from different sources.
"""

from .base import BaseMarketFetcher
from .sina import SinaFetcher
from .tencent import TencentFetcher
from .fetcher_factory import FetcherFactory, get_market_fetcher

# Register all fetchers
FetcherFactory.register("sina", SinaFetcher)
FetcherFactory.register("tencent", TencentFetcher)

__all__ = [
    "BaseMarketFetcher",
    "SinaFetcher",
    "TencentFetcher",
    "FetcherFactory",
    "get_market_fetcher",
]