"""
Tencent Finance Data Fetcher - Alternative to Eastmoney

Data sources:
- Tencent Finance API (qt.gtimg.cn) - Real-time quotes
- Works through proxy that blocks Eastmoney

Features:
- Inherits BaseMarketFetcher interface
- Circuit breaker protection
- curl_cffi for TLS fingerprint bypass
- Unified DataCache integration
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.services.data_cache import get_cache
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Thread pool for sync operations
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tencent_")

# Try to import curl_cffi for TLS fingerprint bypass
try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests

    HAS_CURL_CFFI = False
    logger.warning("[Tencent] curl_cffi not installed, using standard requests")


class TencentFinanceFetcher(BaseMarketFetcher):
    """
    Tencent Finance Data Fetcher

    Uses curl_cffi to bypass TLS fingerprint detection and proxy blocking.

    Usage:
        fetcher = TencentFinanceFetcher()

        # Get real-time quote
        quote = await fetcher.get_quote("sh600519")

        # Get multiple quotes
        quotes = await fetcher.get_quotes(["sh600519", "sz000001"])
    """

    name = "tencent"
    display_name = "腾讯财经数据源"

    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = True
    supports_us = False

    QUOTE_API = "http://qt.gtimg.cn/q="
    KLINE_API = (
        "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"
    )

    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None):
        settings = get_settings()
        self.proxy = settings.get_proxy_url()
        self.cb = circuit_breaker or CircuitBreaker(
            "tencent",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60.0,
            ),
        )
        self._data_cache = get_cache()
        self._cache_lock = asyncio.Lock()

        # Prepare proxies dict for curl_cffi
        if self.proxy:
            self._proxies = {"http": self.proxy, "https": self.proxy}
        else:
            self._proxies = None

    def _make_request(self, url: str, timeout: int = 15) -> Any:
        """Make HTTP request using curl_cffi with browser impersonation."""
        try:
            if HAS_CURL_CFFI:
                response = curl_requests.get(
                    url, timeout=timeout, impersonate="chrome120", proxies=self._proxies
                )
            else:
                response = curl_requests.get(
                    url, timeout=timeout, proxies=self._proxies
                )
            return response
        except Exception as e:
            logger.error(f"[Tencent] Request failed: {e}", exc_info=True)
            raise

    def _parse_tencent_quote(self, data: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Parse Tencent quote response format.

        Format: v_sh600519="1~贵州茅台~600519~1311.00~1315.00~..."

        Fields (separated by ~):
        0: unknown
        1: name
        2: code
        3: latest
        4: prev_close
        5: open
        6: volume (手)
        7: outer_vol
        8: inner_vol
        9: bid1
        10: bid1_vol
        ...
        30: high
        31: low
        32: date_time
        33: change
        34: change_pct
        ...
        """
        try:
            # Extract the data part
            match = re.search(r'v_\w+="(.+)"', data)
            if not match:
                return None

            parts = match.group(1).split("~")
            if len(parts) < 35:
                return None

            name = parts[1]
            code = parts[2]
            latest = float(parts[3]) if parts[3] else None
            prev_close = float(parts[4]) if parts[4] else None
            open_price = float(parts[5]) if parts[5] else None
            volume = int(float(parts[6])) if parts[6] else 0
            high = float(parts[30]) if len(parts) > 30 and parts[30] else None
            low = float(parts[31]) if len(parts) > 31 and parts[31] else None
            date_time = parts[32] if len(parts) > 32 else None
            change = float(parts[33]) if len(parts) > 33 and parts[33] else None
            change_pct = float(parts[34]) if len(parts) > 34 and parts[34] else None

            # Calculate change if not provided
            if change is None and latest and prev_close:
                change = latest - prev_close
            if change_pct is None and latest and prev_close and prev_close != 0:
                change_pct = (change / prev_close) * 100

            return {
                "symbol": symbol,
                "name": name,
                "code": code,
                "latest": latest,
                "open": open_price,
                "high": high,
                "low": low,
                "prev_close": prev_close,
                "change": change,
                "change_pct": round(change_pct, 2) if change_pct else None,
                "volume": volume,
                "source": "tencent",
                "is_demo": False,
                "timestamp": int(datetime.now().timestamp()),
                "date_time": date_time,
            }
        except Exception as e:
            logger.error(f"[Tencent] Parse quote failed: {e}", exc_info=True)
            return None

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get real-time quote for a single symbol.

        Args:
            symbol: Stock symbol with prefix (e.g., "sh600519", "sz000001")

        Returns:
            Quote dict or None if failed
        """
        # Check cache first
        cache_key = f"tencent:quote:{symbol}"
        cached = self._data_cache.get(cache_key)
        if cached:
            return cached

        # Check circuit breaker
        if not self.cb.is_available():
            logger.warning(f"[Tencent] Circuit breaker open for {symbol}")
            return None

        # Normalize symbol
        if not symbol.startswith(("sh", "sz", "hk")):
            if symbol.startswith("6"):
                symbol = f"sh{symbol}"
            elif symbol.startswith(("0", "3")):
                symbol = f"sz{symbol}"

        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    _executor, self._make_request, f"{self.QUOTE_API}{symbol}"
                ),
                timeout=15.0,
            )

            if response.status_code != 200:
                self.cb.record_failure()
                return None

            quote = self._parse_tencent_quote(response.text, symbol)

            if quote:
                self.cb.record_success()
                self._data_cache.set(cache_key, quote, ttl=10)
                return quote
            else:
                self.cb.record_failure()
                return None

        except asyncio.TimeoutError:
            logger.warning(f"[Tencent] Timeout fetching quote for {symbol}")
            self.cb.record_failure()
            return None
        except Exception as e:
            logger.error(
                f"[Tencent] Error fetching quote for {symbol}: {e}", exc_info=True
            )
            self.cb.record_failure()
            return None

    async def get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get real-time quotes for multiple symbols.

        Args:
            symbols: List of stock symbols with prefix

        Returns:
            Dict mapping symbol to quote
        """
        if not symbols:
            return {}

        # Check circuit breaker
        if not self.cb.is_available():
            logger.warning("[Tencent] Circuit breaker open")
            return {}

        # Normalize symbols
        normalized = []
        for s in symbols:
            if not s.startswith(("sh", "sz", "hk")):
                if s.startswith("6"):
                    normalized.append(f"sh{s}")
                elif s.startswith(("0", "3")):
                    normalized.append(f"sz{s}")
                else:
                    normalized.append(s)
            else:
                normalized.append(s)

        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    _executor,
                    self._make_request,
                    f"{self.QUOTE_API}{','.join(normalized)}",
                ),
                timeout=15.0,
            )

            if response.status_code != 200:
                self.cb.record_failure()
                return {}

            # Parse each quote
            results = {}
            lines = response.text.strip().split("\n")

            for i, line in enumerate(lines):
                if i < len(normalized):
                    symbol = normalized[i]
                    quote = self._parse_tencent_quote(line, symbol)
                    if quote:
                        results[symbol] = quote

            if results:
                self.cb.record_success()
            else:
                self.cb.record_failure()

            return results

        except asyncio.TimeoutError:
            logger.warning("[Tencent] Timeout fetching quotes")
            self.cb.record_failure()
            return {}
        except Exception as e:
            logger.error(f"[Tencent] Error fetching quotes: {e}", exc_info=True)
            self.cb.record_failure()
            return {}

    def is_healthy(self) -> bool:
        """Check if fetcher is healthy."""
        return self.cb.is_available()

    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """
        Get K-line (candlestick) data from Sina (works through proxy).

        Args:
            symbol: Stock symbol with prefix (e.g., "sh600519")
            period: "day", "week", "month" (minute not supported)

        Returns:
            List of dicts with keys: date, open, high, low, close, volume
            or None if fetch failed
        """
        if not self.cb.is_available():
            logger.warning(
                f"[Tencent] Circuit breaker open, skipping kline fetch for {symbol}"
            )
            return None

        period_map = {"day": 240, "week": 1200, "month": 5200}
        scale = period_map.get(period, 240)

        url = f"{self.KLINE_API}?symbol={symbol}&scale={scale}&ma=no&datalen=320"

        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(_executor, self._make_request, url, 15),
                timeout=20.0,
            )

            if response.status_code != 200:
                logger.warning(f"[Tencent] K-line API returned {response.status_code}")
                self.cb.record_failure()
                return None

            import json

            data = json.loads(response.text)

            kline_data = []
            for item in data:
                kline_data.append(
                    {
                        "date": item.get("day"),
                        "open": float(item.get("open", 0)),
                        "close": float(item.get("close", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "volume": int(float(item.get("volume", 0))),
                    }
                )

            if kline_data:
                self.cb.record_success()
                return kline_data
            else:
                logger.warning(f"[Tencent] No K-line data found for {symbol}")
                self.cb.record_failure()
                return None

        except asyncio.TimeoutError:
            logger.warning(f"[Tencent] Timeout fetching K-line for {symbol}")
            self.cb.record_failure()
            return None
        except Exception as e:
            logger.error(f"[Tencent] Error fetching K-line: {e}", exc_info=True)
            self.cb.record_failure()
            return None

    def get_kline_sync(
        self, symbol: str, period: str = "day", days: int = 60
    ) -> Optional[List[Dict]]:
        """
        Synchronous K-line fetch for use in thread pool executors.

        This method is designed to be called from synchronous contexts
        (e.g., inside ThreadPoolExecutor) where async/await is not available.

        Args:
            symbol: Stock symbol with prefix (e.g., "sh600519")
            period: "day", "week", "month" (minute not supported)
            days: Number of days of data to return (default 60)

        Returns:
            List of dicts with keys: date, open, high, low, close, volume
            or None if fetch failed
        """
        if not self.cb.is_available():
            logger.warning(
                f"[Tencent] Circuit breaker open, skipping kline fetch for {symbol}"
            )
            return None

        period_map = {"day": 240, "week": 1200, "month": 5200}
        scale = period_map.get(period, 240)

        # Request more data than needed, then truncate
        url = f"{self.KLINE_API}?symbol={symbol}&scale={scale}&ma=no&datalen=320"

        try:
            response = self._make_request(url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"[Tencent] K-line API returned {response.status_code}")
                self.cb.record_failure()
                return None

            import json

            data = json.loads(response.text)

            kline_data = []
            for item in data:
                kline_data.append(
                    {
                        "date": item.get("day"),
                        "open": float(item.get("open", 0)),
                        "close": float(item.get("close", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "volume": int(float(item.get("volume", 0))),
                    }
                )

            if kline_data:
                self.cb.record_success()
                # Return last N days
                return kline_data[-days:] if len(kline_data) > days else kline_data
            else:
                logger.warning(f"[Tencent] No K-line data found for {symbol}")
                self.cb.record_failure()
                return None

        except Exception as e:
            logger.error(f"[Tencent] Error fetching K-line sync: {e}", exc_info=True)
            self.cb.record_failure()
            return None

    async def reset_circuit_breaker(self) -> dict:
        """Reset circuit breaker manually."""
        from app.services.circuit_breaker import CircuitState

        async with self._cache_lock:
            old_state = self.cb.state.value
            self.cb._stats._consecutive_failures = 0
            self.cb._stats._consecutive_successes = 0
            self.cb._stats._last_failure_time = None
            self.cb._state = CircuitState.CLOSED

            logger.info(
                f"[Tencent] Circuit breaker manually reset: {old_state} -> closed"
            )

            return {
                "success": True,
                "state": "closed",
                "message": "Circuit breaker reset successfully",
            }

    def get_circuit_breaker_status(self) -> dict:
        """Get circuit breaker status for admin panel."""
        return {
            "is_available": self.cb.is_available(),
            "state": self.cb.state.value,
            "consecutive_failures": self.cb._stats.consecutive_failures,
            "consecutive_successes": self.cb._stats.consecutive_successes,
        }


# Singleton instance
tencent_fetcher = TencentFinanceFetcher()


def get_tencent_fetcher() -> TencentFinanceFetcher:
    """Get the singleton TencentFinanceFetcher instance."""
    return tencent_fetcher


def get_circuit_breaker_status() -> dict:
    """Get circuit breaker status for admin panel."""
    return tencent_fetcher.get_circuit_breaker_status()
