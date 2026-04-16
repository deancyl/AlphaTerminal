import httpx
from typing import Optional, Dict, Any, List
import asyncio
from .base import BaseMarketFetcher

class SinaFetcher(BaseMarketFetcher):
    """
    Sina Finance data fetcher.
    
    Supports: A-shares, indices, basic quote and K-line data.
    Does NOT support: Order book (Level 2), futures, HK, US stocks.
    """
    
    name = "sina"
    display_name = "新浪财经"
    
    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = False
    
    BASE_URL = "https://hq.sinajs.cn"
    KLINESINA_URL = "https://quotes.sina.cn/cn/api/quotes.php"
    
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
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self._client
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Sina format (sh600519, sz000001)."""
        symbol = symbol.lower().strip()
        if symbol.startswith("sh") or symbol.startswith("sz"):
            return symbol
        # Assume numeric code, determine exchange
        if symbol.startswith("6"):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get real-time quote from Sina."""
        try:
            client = await self._get_client()
            sina_code = self._normalize_symbol(symbol)
            
            url = f"{self.BASE_URL}/list={sina_code}"
            resp = await client.get(url)
            resp.encoding = 'gbk'
            
            if resp.status_code != 200:
                return None
            
            text = resp.text
            # Parse Sina response format: var hq_str_sh600519="...";
            if '="' not in text:
                return None
            
            data_str = text.split('="')[1].rstrip('";')
            fields = data_str.split(',')
            
            if len(fields) < 33:
                return None
            
            # Sina format: name, open, prev_close, price, high, low, ...
            name = fields[0]
            open_price = float(fields[1]) if fields[1] else 0
            prev_close = float(fields[2]) if fields[2] else 0
            price = float(fields[3]) if fields[3] else 0
            high = float(fields[4]) if fields[4] else 0
            low = float(fields[5]) if fields[5] else 0
            volume = int(fields[8]) if fields[8] else 0
            
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
            
            return {
                "symbol": symbol,
                "name": name,
                "price": price,
                "open": open_price,
                "high": high,
                "low": low,
                "prev_close": prev_close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "source": "sina"
            }
            
        except Exception as e:
            # Log error but don't expose details
            return None
    
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """Get K-line data from Sina."""
        try:
            client = await self._get_client()
            sina_code = self._normalize_symbol(symbol)
            
            # Map period to Sina format
            period_map = {
                "minute": "min",
                "day": "day",
                "week": "week",
                "month": "month"
            }
            sina_period = period_map.get(period, "day")
            
            url = f"{self.KLINESINA_URL}?symbol={sina_code}&scale=240&datalen=200"
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            if not data or "data" not in data:
                return None
            
            klines = []
            for item in data["data"]:
                klines.append({
                    "date": item.get("d", ""),
                    "open": float(item.get("o", 0)),
                    "high": float(item.get("h", 0)),
                    "low": float(item.get("l", 0)),
                    "close": float(item.get("c", 0)),
                    "volume": int(item.get("v", 0))
                })
            
            return klines
            
        except Exception:
            return None
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None