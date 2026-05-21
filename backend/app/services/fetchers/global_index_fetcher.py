"""
Global Index Data Fetcher
Multi-source data fetching for global market indices

Supports:
- Americas: SPX, IXIC, DJI, RUT, VIX, TSX, IBOV
- Europe: UKX, DAX, CAC, SMI, IBEX
- Asia-Pacific: N225, HSI, KS11, AXJO, NSEI

Data sources (free):
1. Tencent Finance (qt.gtimg.cn) - Primary for HK/US/CN
2. Yahoo Finance (query1.finance.yahoo.com) - Fallback for global
3. Alpha Vantage (free tier) - Last resort

Circuit Breaker: 5 consecutive failures → OPEN, 60s timeout
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import httpx
import re
import json

from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="global_index_")

_GLOBAL_INDEX_CB = CircuitBreaker(
    CircuitBreakerConfig(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0
    )
)

# Global index configuration
GLOBAL_INDEX_SYMBOLS = {
    "Americas": ["SPX", "IXIC", "DJI", "RUT", "VIX", "TSX", "IBOV"],
    "Europe": ["UKX", "DAX", "CAC", "SMI", "IBEX"],
    "Asia-Pacific": ["N225", "HSI", "KS11", "AXJO", "NSEI"]
}

# Index metadata
INDEX_METADATA = {
    # Americas
    "SPX": {"name": "标普500", "name_en": "S&P 500", "flag": "🇺🇸", "market": "US", "currency": "USD"},
    "IXIC": {"name": "纳斯达克", "name_en": "NASDAQ", "flag": "🇺🇸", "market": "US", "currency": "USD"},
    "DJI": {"name": "道琼斯", "name_en": "Dow Jones", "flag": "🇺🇸", "market": "US", "currency": "USD"},
    "RUT": {"name": "罗素2000", "name_en": "Russell 2000", "flag": "🇺🇸", "market": "US", "currency": "USD"},
    "VIX": {"name": "波动率指数", "name_en": "VIX", "flag": "🇺🇸", "market": "US", "currency": "USD"},
    "TSX": {"name": "多伦多综指", "name_en": "S&P/TSX", "flag": "🇨🇦", "market": "CA", "currency": "CAD"},
    "IBOV": {"name": "巴西博维斯帕", "name_en": "Bovespa", "flag": "🇧🇷", "market": "BR", "currency": "BRL"},
    # Europe
    "UKX": {"name": "富时100", "name_en": "FTSE 100", "flag": "🇬🇧", "market": "UK", "currency": "GBP"},
    "DAX": {"name": "德国DAX", "name_en": "DAX", "flag": "🇩🇪", "market": "DE", "currency": "EUR"},
    "CAC": {"name": "法国CAC40", "name_en": "CAC 40", "flag": "🇫🇷", "market": "FR", "currency": "EUR"},
    "SMI": {"name": "瑞士SMI", "name_en": "SMI", "flag": "🇨🇭", "market": "CH", "currency": "CHF"},
    "IBEX": {"name": "西班牙IBEX35", "name_en": "IBEX 35", "flag": "🇪🇸", "market": "ES", "currency": "EUR"},
    # Asia-Pacific
    "N225": {"name": "日经225", "name_en": "Nikkei 225", "flag": "🇯🇵", "market": "JP", "currency": "JPY"},
    "HSI": {"name": "恒生指数", "name_en": "Hang Seng", "flag": "🇭🇰", "market": "HK", "currency": "HKD"},
    "KS11": {"name": "韩国KOSPI", "name_en": "KOSPI", "flag": "🇰🇷", "market": "KR", "currency": "KRW"},
    "AXJO": {"name": "澳洲标普200", "name_en": "S&P/ASX 200", "flag": "🇦🇺", "market": "AU", "currency": "AUD"},
    "NSEI": {"name": "印度NIFTY50", "name_en": "NIFTY 50", "flag": "🇮🇳", "market": "IN", "currency": "INR"},
}

# Yahoo Finance symbol mapping (Tencent uses different symbols)
YAHOO_SYMBOL_MAP = {
    "SPX": "^GSPC",
    "IXIC": "^IXIC",
    "DJI": "^DJI",
    "RUT": "^RUT",
    "VIX": "^VIX",
    "TSX": "^GSPTSE",
    "IBOV": "^BVSP",
    "UKX": "^FTSE",
    "DAX": "^GDAXI",
    "CAC": "^FCHI",
    "SMI": "^SSMI",
    "IBEX": "^IBEX",
    "N225": "^N225",
    "HSI": "^HSI",
    "KS11": "^KS11",
    "AXJO": "^AXJO",
    "NSEI": "^NSEI",
}

# Tencent symbol mapping
TENCENT_SYMBOL_MAP = {
    "SPX": "gb_$spx",
    "IXIC": "gb_$ndx",
    "DJI": "gb_$dji",
    "RUT": "gb_$rut",
    "VIX": "gb_$vix",
    "N225": "gb_$n225",
    "HSI": "hkHSI",
}


@dataclass
class IndexQuote:
    """Index quote data"""
    symbol: str
    name: str
    name_en: str
    flag: str
    market: str
    currency: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    timestamp: str
    is_mock: bool = False
    sparkline: Optional[List[float]] = None


class GlobalIndexFetcher:
    """Multi-source global index data fetcher"""
    
    def __init__(self):
        self._cache: Dict[str, Tuple[float, IndexQuote]] = {}
        self._sparkline_cache: Dict[str, Tuple[float, List[float]]] = {}
        self._lock = threading.Lock()
        self._ttl = 60  # 1 minute cache
        self._sparkline_ttl = 300  # 5 minutes for sparklines
        
        # HTTP client configuration
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        
        # Proxy configuration from environment
        self._proxy = None
        import os
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if http_proxy:
            self._proxy = http_proxy
    
    async def fetch_all_quotes(self) -> List[IndexQuote]:
        """Fetch quotes for all configured indices"""
        if not _GLOBAL_INDEX_CB.is_available():
            logger.warning("[GlobalIndex] Circuit breaker OPEN, using mock fallback")
            all_symbols = []
            for region_symbols in GLOBAL_INDEX_SYMBOLS.values():
                all_symbols.extend(region_symbols)
            return [self._create_mock_quote(s) for s in all_symbols]
        
        all_symbols = []
        for region_symbols in GLOBAL_INDEX_SYMBOLS.values():
            all_symbols.extend(region_symbols)
        
        results = []
        success_count = 0
        failure_count = 0
        tasks = [self._fetch_single_quote(symbol) for symbol in all_symbols]
        quotes = await asyncio.gather(*tasks, return_exceptions=True)
        
        for symbol, quote in zip(all_symbols, quotes):
            if isinstance(quote, Exception):
                logger.warning(f"[GlobalIndex] Failed to fetch {symbol}: {quote}")
                failure_count += 1
                cached = self._get_cached_quote(symbol)
                if cached:
                    results.append(cached)
                else:
                    results.append(self._create_mock_quote(symbol))
            else:
                success_count += 1
                results.append(quote)
        
        if success_count > failure_count:
            _GLOBAL_INDEX_CB.record_success()
        else:
            _GLOBAL_INDEX_CB.record_failure()
        
        return results
    
    async def _fetch_single_quote(self, symbol: str) -> IndexQuote:
        """Fetch quote for a single index"""
        cached = self._get_cached_quote(symbol)
        if cached:
            return cached
        
        if symbol in TENCENT_SYMBOL_MAP:
            try:
                quote = await self._fetch_from_tencent(symbol)
                if quote:
                    self._cache_quote(quote)
                    return quote
            except Exception as e:
                logger.debug(f"[GlobalIndex] Tencent failed for {symbol}: {e}")
        
        try:
            quote = await self._fetch_from_yahoo(symbol)
            if quote:
                self._cache_quote(quote)
                return quote
        except Exception as e:
            logger.debug(f"[GlobalIndex] Yahoo failed for {symbol}: {e}")
        
        # Last resort: mock data
        raise Exception(f"All data sources failed for {symbol}")
    
    async def _fetch_from_tencent(self, symbol: str) -> Optional[IndexQuote]:
        """Fetch from Tencent Finance API"""
        tencent_symbol = TENCENT_SYMBOL_MAP.get(symbol)
        if not tencent_symbol:
            return None
        
        url = f"https://qt.gtimg.cn/q={tencent_symbol}"
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            if self._proxy:
                client = httpx.AsyncClient(timeout=5.0, proxies=self._proxy)
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            
            # Parse Tencent format: v_symbol="1~name~code~price~..."
            text = resp.text
            match = re.search(r'v_([^=]+)="([^"]+)"', text)
            if not match:
                return None
            
            fields = match.group(2).split("~")
            if len(fields) < 35:
                return None
            
            meta = INDEX_METADATA.get(symbol, {})
            
            return IndexQuote(
                symbol=symbol,
                name=meta.get("name", fields[1]),
                name_en=meta.get("name_en", ""),
                flag=meta.get("flag", "🌍"),
                market=meta.get("market", "XX"),
                currency=meta.get("currency", "USD"),
                price=float(fields[3]) if fields[3] else 0,
                change_pct=float(fields[32]) if fields[32] else 0,
                open=float(fields[5]) if fields[5] else 0,
                high=float(fields[33]) if fields[33] else 0,
                low=float(fields[34]) if fields[34] else 0,
                volume=int(float(fields[6])) if fields[6] else 0,
                timestamp=fields[30][-8:] if len(fields[30]) > 8 else fields[30],
                is_mock=False,
            )
    
    async def _fetch_from_yahoo(self, symbol: str) -> Optional[IndexQuote]:
        """Fetch from Yahoo Finance API"""
        yahoo_symbol = YAHOO_SYMBOL_MAP.get(symbol)
        if not yahoo_symbol:
            return None
        
        # Yahoo Finance v8 API
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {
            "interval": "1d",
            "range": "1d",
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            if self._proxy:
                client = httpx.AsyncClient(timeout=10.0, proxies=self._proxy)
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            
            quote_data = result[0]
            meta = quote_data.get("meta", {})
            indicators = quote_data.get("indicators", {}).get("quote", [{}])[0]
            
            index_meta = INDEX_METADATA.get(symbol, {})
            
            # Get latest values
            closes = indicators.get("close", [])
            opens = indicators.get("open", [])
            highs = indicators.get("high", [])
            lows = indicators.get("low", [])
            volumes = indicators.get("volume", [])
            
            price = closes[-1] if closes else meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose", price)
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
            
            return IndexQuote(
                symbol=symbol,
                name=index_meta.get("name") or meta.get("shortName") or symbol,
                name_en=index_meta.get("name_en") or meta.get("shortName") or "",
                flag=index_meta.get("flag", "🌍"),
                market=index_meta.get("market", "XX"),
                currency=index_meta.get("currency") or meta.get("currency") or "USD",
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                open=round(opens[-1], 2) if opens else 0,
                high=round(highs[-1], 2) if highs else 0,
                low=round(lows[-1], 2) if lows else 0,
                volume=int(volumes[-1]) if volumes else 0,
                timestamp=datetime.now().strftime("%H:%M"),
                is_mock=False,
            )
    
    async def fetch_kline_history(
        self, 
        symbol: str, 
        period: str = "daily",
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch K-line history for an index
        
        Args:
            symbol: Index symbol (e.g., "HSI", "SPX")
            period: "daily" or "weekly"
            limit: Number of bars to fetch (1-500)
        
        Returns:
            List of OHLCV dicts
        """
        yahoo_symbol = YAHOO_SYMBOL_MAP.get(symbol)
        if not yahoo_symbol:
            raise ValueError(f"Unknown symbol: {symbol}")
        
        # Calculate range based on limit
        if period == "weekly":
            range_str = f"{min(limit // 5 + 1, 104)}w"  # Max 2 years weekly
        else:
            range_str = f"{min(limit + 30, 730)}d"  # Max 2 years daily
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        params = {
            "interval": "1wk" if period == "weekly" else "1d",
            "range": range_str,
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            if self._proxy:
                client = httpx.AsyncClient(timeout=15.0, proxies=self._proxy)
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if not result:
                return []
            
            quote_data = result[0]
            timestamps = quote_data.get("timestamp", [])
            indicators = quote_data.get("indicators", {}).get("quote", [{}])[0]
            
            opens = indicators.get("open", [])
            closes = indicators.get("close", [])
            highs = indicators.get("high", [])
            lows = indicators.get("low", [])
            volumes = indicators.get("volume", [])
            
            klines = []
            for i in range(len(timestamps)):
                if i >= len(closes):
                    break
                    
                # Skip None values
                if closes[i] is None:
                    continue
                
                dt = datetime.fromtimestamp(timestamps[i])
                klines.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "open": round(opens[i], 2) if opens[i] else 0,
                    "high": round(highs[i], 2) if highs[i] else 0,
                    "low": round(lows[i], 2) if lows[i] else 0,
                    "close": round(closes[i], 2),
                    "volume": int(volumes[i]) if volumes[i] else 0,
                    "change_pct": round((closes[i] - closes[i-1]) / closes[i-1] * 100, 2) if i > 0 and closes[i-1] else 0,
                })
            
            # Return last N bars
            return klines[-limit:]
    
    async def fetch_sparkline(self, symbol: str, days: int = 20) -> List[float]:
        """
        Fetch sparkline data (last N close prices)
        
        Args:
            symbol: Index symbol
            days: Number of days (default 20)
        
        Returns:
            List of close prices
        """
        # Check cache
        cached = self._get_cached_sparkline(symbol)
        if cached:
            return cached
        
        try:
            klines = await self.fetch_kline_history(symbol, "daily", days)
            sparkline = [k["close"] for k in klines]
            
            # Cache it
            self._cache_sparkline(symbol, sparkline)
            
            return sparkline
        except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
            logger.warning(f"[HTTP] sparkline for {symbol}: {e}", exc_info=True)
            return []
    
    def _cache_quote(self, quote: IndexQuote):
        """Cache a quote"""
        with self._lock:
            self._cache[quote.symbol] = (time.time(), quote)
    
    def _get_cached_quote(self, symbol: str) -> Optional[IndexQuote]:
        """Get cached quote if not expired"""
        with self._lock:
            if symbol in self._cache:
                timestamp, quote = self._cache[symbol]
                if time.time() - timestamp < self._ttl:
                    return quote
        return None
    
    def _cache_sparkline(self, symbol: str, data: List[float]):
        """Cache sparkline data"""
        with self._lock:
            self._sparkline_cache[symbol] = (time.time(), data)
    
    def _get_cached_sparkline(self, symbol: str) -> Optional[List[float]]:
        """Get cached sparkline if not expired"""
        with self._lock:
            if symbol in self._sparkline_cache:
                timestamp, data = self._sparkline_cache[symbol]
                if time.time() - timestamp < self._sparkline_ttl:
                    return data
        return None
    
    def _create_mock_quote(self, symbol: str) -> IndexQuote:
        """Create mock quote for fallback"""
        meta = INDEX_METADATA.get(symbol, {
            "name": symbol,
            "name_en": symbol,
            "flag": "🌍",
            "market": "XX",
            "currency": "USD"
        })
        
        # Generate realistic mock price based on symbol
        mock_prices = {
            "SPX": 4200, "IXIC": 14500, "DJI": 33500, "RUT": 1980, "VIX": 18.5,
            "TSX": 21500, "IBOV": 125000, "UKX": 7800, "DAX": 16500, "CAC": 7400,
            "SMI": 11200, "IBEX": 11500, "N225": 32500, "HSI": 18500, "KS11": 2650,
            "AXJO": 7600, "NSEI": 22500,
        }
        
        base_price = mock_prices.get(symbol, 1000)
        import random
        change_pct = round(random.uniform(-2, 2), 2)
        price = round(base_price * (1 + change_pct / 100), 2)
        
        return IndexQuote(
            symbol=symbol,
            name=meta.get("name", symbol),
            name_en=meta.get("name_en", symbol),
            flag=meta.get("flag", "🌍"),
            market=meta.get("market", "XX"),
            currency=meta.get("currency", "USD"),
            price=price,
            change_pct=change_pct,
            open=round(price * 0.998, 2),
            high=round(price * 1.005, 2),
            low=round(price * 0.995, 2),
            volume=0,
            timestamp=datetime.now().strftime("%H:%M"),
            is_mock=True,
        )


# Singleton instance
_fetcher = GlobalIndexFetcher()


def get_global_index_fetcher() -> GlobalIndexFetcher:
    """Get the singleton fetcher instance"""
    return _fetcher
