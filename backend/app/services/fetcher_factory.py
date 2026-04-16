from typing import Optional, Dict, Type, List
from .base import BaseMarketFetcher
from .sina import SinaFetcher

class FetcherFactory:
    """
    Factory for creating market data fetchers.
    
    Enables dynamic switching between different data sources.
    """
    
    _fetchers: Dict[str, Type[BaseMarketFetcher]] = {
        "sina": SinaFetcher,
        # Future: "tencent": TencentFetcher,
        # Future: "eastmoney": EastmoneyFetcher,
    }
    
    _current_fetcher: Optional[str] = "sina"
    _proxy: Optional[str] = None
    
    @classmethod
    def register(cls, name: str, fetcher_class: Type[BaseMarketFetcher]):
        """Register a new fetcher type."""
        cls._fetchers[name] = fetcher_class
    
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
    def set_current(cls, name: str) -> bool:
        """
        Set the current default fetcher.
        
        Args:
            name: Fetcher name to use as default.
            
        Returns:
            True if successful, False if fetcher not found.
        """
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
        """
        Get information about a fetcher.
        
        Returns:
            Dict with name, display_name, supported_features
        """
        if name not in cls._fetchers:
            return None
        
        fetcher_class = cls._fetchers[name]
        return {
            "name": fetcher_class.name,
            "display_name": fetcher_class.display_name,
            "supported_features": fetcher_class.supported_features,
        }
    
    @classmethod
    def set_proxy(cls, proxy: Optional[str]):
        """Set proxy for all fetchers."""
        cls._proxy = proxy
    
    @classmethod
    def get_proxy(cls) -> Optional[str]:
        """Get current proxy setting."""
        return cls._proxy

# Convenience function
def get_market_fetcher(name: Optional[str] = None) -> Optional[BaseMarketFetcher]:
    """Get market fetcher instance."""
    return FetcherFactory.get_fetcher(name)