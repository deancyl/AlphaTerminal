import httpx
from typing import Optional, Dict, Any, List
from .base import BaseMarketFetcher

class EastmoneyFetcher(BaseMarketFetcher):
    """
    Eastmoney (东方财富) data fetcher.
    
    Supports: A-shares, indices, futures, HK stocks, US stocks.
    """
    
    name = "eastmoney"
    display_name = "东方财富"
    
    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = True
    supports_hk = True
    supports_us = True
    
    BASE_URL = "https://push2.eastmoney.com"
    KLINE_URL = "https://push2his.eastmoney.com"
    
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proxy support."""
        if self._client is None:
            proxies = {"all://": self.proxy} if self.proxy else None
            self._client = httpx.AsyncClient(
                proxies=proxies,
                timeout=10.0,
                headers={
                    "Referer": "https://www.eastmoney.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._client
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Eastmoney format."""
        symbol = symbol.lower().strip()
        
        # Already normalized
        if symbol.startswith(("sh", "sz", "hk", "us")):
            return symbol
        
        # Numeric code - assume A-share
        if symbol.startswith("6"):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time quote from Eastmoney."""
        try:
            client = await self._get_client()
            em_code = self._normalize_symbol(symbol)
            
            # Eastmoney quote API
            url = f"{self.BASE_URL}/api/qt/stock/get"
            params = {
                "secid": self._to_em_secid(em_code),
                "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
            
            resp = await client.get(url, params=params)
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if not data or "data" not in data:
                return None
            
            d = data["data"]
            
            return {
                "symbol": symbol,
                "name": d.get("f58", symbol),
                "price": float(d.get("f43", 0)) / 100 if d.get("f43") else 0,
                "open": float(d.get("f46", 0)) / 100 if d.get("f46") else 0,
                "high": float(d.get("f44", 0)) / 100 if d.get("f44") else 0,
                "low": float(d.get("f45", 0)) / 100 if d.get("f45") else 0,
                "prev_close": float(d.get("f60", 0)) / 100 if d.get("f60") else 0,
                "volume": int(d.get("f47", 0)) if d.get("f47") else 0,
                "change_pct": float(d.get("f170", 0)) / 100 if d.get("f170") else 0,
                "source": "eastmoney"
            }
            
        except Exception:
            return None
    
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """Get K-line data from Eastmoney."""
        try:
            client = await self._get_client()
            em_code = self._normalize_symbol(symbol)
            
            # Map period to Eastmoney format
            period_map = {
                "minute": "101",
                "day": "101",
                "week": "102",
                "month": "103"
            }
            em_period = period_map.get(period, "101")
            
            url = f"{self.KLINE_URL}/api/qt/stock/kline/get"
            params = {
                "secid": self._to_em_secid(em_code),
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "klt": em_period,
                "fqt": "1",
                "beg": "0",
                "end": "20500101",
                "lmt": "200",
            }
            
            resp = await client.get(url, params=params)
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if not data or "data" not in data or not data["data"].get("klines"):
                return None
            
            klines = []
            for item in data["data"]["klines"]:
                fields = item.split(",")
                if len(fields) >= 6:
                    klines.append({
                        "date": fields[0],
                        "open": float(fields[1]),
                        "high": float(fields[2]),
                        "low": float(fields[3]),
                        "close": float(fields[4]),
                        "volume": int(fields[5]) if len(fields) > 5 else 0
                    })
            
            return klines
            
        except Exception:
            return None
    
    def _to_em_secid(self, symbol: str) -> str:
        """Convert symbol to Eastmoney secid format."""
        if symbol.startswith("sh"):
            return f"1.{symbol[2:]}"
        elif symbol.startswith("sz"):
            return f"0.{symbol[2:]}"
        elif symbol.startswith("hk"):
            return f"116.{symbol[2:]}"
        elif symbol.startswith("us"):
            return f"105.{symbol[2:]}"
        return symbol
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None