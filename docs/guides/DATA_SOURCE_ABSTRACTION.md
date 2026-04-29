# Data Source Abstraction Layer Design

## Overview
Create a unified data fetcher factory to eliminate hardcoded data sources (Sina, Tencent, Eastmoney) and enable dynamic switching.

## Architecture

### 1. Base Interface
```python
# backend/app/services/fetchers/base.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseMarketFetcher(ABC):
    """Base interface for all market data fetchers"""
    
    name: str = "base"
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time quote for a symbol"""
        pass
    
    @abstractmethod
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[list]:
        """Get K-line data"""
        pass
    
    @abstractmethod
    async def get_order_book(self, symbol: str) -> Optional[Dict]:
        """Get order book (may return None if not supported)"""
        pass
    
    @property
    @abstractmethod
    def supported_features(self) -> list:
        """Return list of supported features"""
        pass
```

### 2. Implementations
- SinaFetcher (current default)
- TencentFetcher (backup)
- EastmoneyFetcher (alternative)

### 3. Factory & Manager
```python
# backend/app/services/fetcher_factory.py
class FetcherFactory:
    _fetchers = {
        "sina": SinaFetcher,
        "tencent": TencentFetcher,
        "eastmoney": EastmoneyFetcher,
    }
    
    @classmethod
    def get_fetcher(cls, name: str) -> BaseMarketFetcher:
        if name not in cls._fetchers:
            raise ValueError(f"Unknown fetcher: {name}")
        return cls._fetchers[name]()
    
    @classmethod
    def list_fetchers(cls) -> list:
        return list(cls._fetchers.keys())
```

### 4. Circuit Breaker
- Auto-failover when primary source fails
- Health check counter
- Automatic fallback to backup source

## Implementation Plan
1. Create base interface
2. Implement SinaFetcher (extract from current code)
3. Create FetcherFactory
4. Update market.py routes to use factory
5. Add health check and circuit breaker
6. Update AdminDashboard to show fetcher status

## Priority: HIGH
## Estimated Time: 16 hours
