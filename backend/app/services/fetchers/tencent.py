import httpx
from typing import Optional, Dict, Any, List
from .base import BaseMarketFetcher
from ..http_client import get_shared_client


class TencentFetcher(BaseMarketFetcher):
    """
    Tencent Finance data fetcher.
    
    Supports: A-shares, indices, HK stocks, US stocks.
    Does NOT support: Order book (Level 2), futures.
    
    Uses shared HTTP client for connection pooling.
    """
    
    name = "tencent"
    display_name = "腾讯财经"
    
    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = True
    supports_us = True
    
    BASE_URL = "https://qt.gtimg.cn"
    KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    
    def __init__(self, proxy: Optional[str] = None):
        pass
    
    async def _get_client(self) -> httpx.AsyncClient:
        return await get_shared_client()
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Tencent format (sh600519, sz000001, hk00700)."""
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
        """Get real-time quote from Tencent."""
        try:
            client = await self._get_client()
            tencent_code = self._normalize_symbol(symbol)
            
            url = f"{self.BASE_URL}/q={tencent_code}"
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return None
            
            text = resp.text
            if '="' not in text:
                return None
            
            data_str = text.split('="')[1].rstrip('";')
            fields = data_str.split('~')
            
            if len(fields) < 40:
                return None
            
            # Tencent format: various fields
            name = fields[1] if len(fields) > 1 else symbol
            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[4]) if fields[4] else 0
            open_ = float(fields[5]) if fields[5] else 0
            volume = int(fields[6]) if fields[6] else 0
            high = float(fields[33]) if fields[33] else 0
            low = float(fields[34]) if fields[34] else 0
            
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
            
            return {
                "symbol": symbol,
                "name": name,
                "price": price,
                "open": open_,
                "high": high,
                "low": low,
                "prev_close": prev_close,
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "source": "tencent"
            }
            
        except Exception:
            return None
    
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """Get K-line data from Tencent."""
        try:
            client = await self._get_client()
            tencent_code = self._normalize_symbol(symbol)
            
            # Map period to Tencent format
            period_map = {
                "minute": "1",
                "day": "day",
                "week": "week",
                "month": "month"
            }
            tencent_period = period_map.get(period, "day")
            
            url = f"{self.KLINE_URL}?_var=kline_dayqfq&param={tencent_code},{tencent_period},,,,320,qfq"
            resp = await client.get(url)
            
            if resp.status_code != 200:
                return None
            
            text = resp.text
            # Parse: var kline_dayqfq={...}
            if "=" not in text:
                return None
            
            import json
            data_str = text.split("=")[1]
            data = json.loads(data_str)
            
            if "data" not in data:
                return None
            
            symbol_data = data["data"].get(tencent_code, {})
            qfqday = symbol_data.get("qfqday", [])
            
            klines = []
            for item in qfqday:
                if len(item) >= 5:
                    klines.append({
                        "date": item[0],
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": int(item[5]) if len(item) > 5 else 0
                    })
            
            return klines
            
        except Exception:
            return None