from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

class BaseMarketFetcher(ABC):
    """
    Base interface for all market data fetchers.
    
    This abstract class defines the contract that all data fetchers must implement.
    It enables dynamic switching between different data sources (Sina, Tencent, Eastmoney, etc.)
    """
    
    name: str = "base"
    display_name: str = "Base Fetcher"
    
    # Feature flags - what this fetcher supports
    supports_quote: bool = True
    supports_kline: bool = True
    supports_order_book: bool = False
    supports_futures: bool = False
    supports_hk: bool = False
    supports_us: bool = False
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., "sh600519", "sz000001")
            
        Returns:
            Dict with keys: name, price, change_pct, volume, open, high, low, prev_close
            or None if fetch failed
        """
        pass
    
    @abstractmethod
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """
        Get K-line (candlestick) data.
        
        Args:
            symbol: Stock symbol
            period: "minute", "day", "week", "month"
            
        Returns:
            List of dicts with keys: date, open, high, low, close, volume
            or None if fetch failed
        """
        pass
    
    async def get_order_book(self, symbol: str) -> Optional[Dict]:
        """
        Get order book (Level 2 data).
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with keys: asks, bids (each is list of {price, volume})
            or None if not supported or fetch failed
        """
        # Default: not supported
        return None
    
    async def get_futures_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get futures quote.
        
        Args:
            symbol: Futures symbol
            
        Returns:
            Quote dict or None if not supported
        """
        # Default: not supported
        return None
    
    @property
    def supported_features(self) -> List[str]:
        """Return list of supported features for this fetcher."""
        features = []
        if self.supports_quote:
            features.append("quote")
        if self.supports_kline:
            features.append("kline")
        if self.supports_order_book:
            features.append("order_book")
        if self.supports_futures:
            features.append("futures")
        if self.supports_hk:
            features.append("hk_stocks")
        if self.supports_us:
            features.append("us_stocks")
        return features
    
    def is_healthy(self) -> bool:
        """
        Check if this fetcher is healthy.
        Can be overridden to implement health checks.
        """
        return True
    
    async def ping(self) -> bool:
        """
        Ping the data source to check connectivity.
        
        Returns:
            True if reachable, False otherwise
        """
        try:
            # Try to fetch a well-known symbol
            result = await self.get_quote("sh000001")
            return result is not None
        except Exception:
            return False