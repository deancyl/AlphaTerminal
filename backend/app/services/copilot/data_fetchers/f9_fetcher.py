"""
F9 Data Fetcher for AlphaTerminal Copilot

直接调用 router 函数获取 F9 深度数据，支持缓存和熔断器保护。
"""

import asyncio
import logging
import threading
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.data_cache import get_cache
from app.routers.f9_deep import (
    get_financial_data,
    get_institution_holdings,
    get_margin_data,
    get_profit_forecast,
    get_shareholder_data,
    get_announcements,
    get_peer_comparison,
    normalize_f9_symbol,
)
from app.services.circuit_breaker import CircuitBreakerOpen

logger = logging.getLogger(__name__)

# 默认获取的 tabs
DEFAULT_TABS = ["financial", "institution", "forecast", "shareholder"]

# 缓存 TTL: 5 分钟
CACHE_TTL = 300


@dataclass
class F9DataResult:
    """F9 数据结果"""
    symbol: str
    financial: Optional[Dict[str, Any]] = None
    institution: Optional[Dict[str, Any]] = None
    forecast: Optional[Dict[str, Any]] = None
    shareholder: Optional[Dict[str, Any]] = None
    margin: Optional[Dict[str, Any]] = None
    peers: Optional[Dict[str, Any]] = None
    announcements: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None


class F9Fetcher:
    """
    F9 深度数据获取器

    直接调用 router 函数获取数据，支持缓存和熔断器保护。
    """

    def __init__(self):
        self._cache = get_cache()
        self._namespace = "copilot:f9:"

    def _get_cache_key(self, symbol: str, tab: str) -> str:
        """生成缓存键"""
        return f"{self._namespace}{symbol}:{tab}"

    def _get_from_cache(self, symbol: str, tab: str) -> Optional[Dict[str, Any]]:
        """从缓存获取数据"""
        key = self._get_cache_key(symbol, tab)
        return self._cache.get(key)

    def _set_to_cache(self, symbol: str, tab: str, data: Dict[str, Any]) -> None:
        """设置缓存"""
        key = self._get_cache_key(symbol, tab)
        self._cache.set(key, data, ttl=CACHE_TTL)

    def _extract_data(self, response: Any) -> Optional[Any]:
        """
        从 success_response 中提取 data 字段

        Args:
            response: Router 返回的响应对象

        Returns:
            data 字段内容，或 None
        """
        if response is None:
            return None

        # 检查是否是 success_response 格式
        if hasattr(response, 'get') and callable(response.get):
            # 字典-like 对象
            if response.get('code') == 0:
                return response.get('data')
            else:
                # 错误响应
                error_msg = response.get('message', 'Unknown error')
                logger.warning(f"[F9Fetcher] Router returned error: {error_msg}")
                return None
        elif isinstance(response, dict):
            if response.get('code') == 0:
                return response.get('data')
            else:
                error_msg = response.get('message', 'Unknown error')
                logger.warning(f"[F9Fetcher] Router returned error: {error_msg}")
                return None

        # 尝试直接返回（某些响应可能直接是 data）
        return response if isinstance(response, dict) else None

    async def _fetch_financial(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取财务数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "financial")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: financial:{symbol}")
                return cached

        try:
            response = await get_financial_data(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "financial", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for financial:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching financial for {symbol}: {e}")
            return None

    async def _fetch_institution(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取机构持股数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "institution")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: institution:{symbol}")
                return cached

        try:
            response = await get_institution_holdings(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "institution", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for institution:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching institution for {symbol}: {e}")
            return None

    async def _fetch_forecast(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取盈利预测数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "forecast")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: forecast:{symbol}")
                return cached

        try:
            response = await get_profit_forecast(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "forecast", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for forecast:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching forecast for {symbol}: {e}")
            return None

    async def _fetch_shareholder(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取股东研究数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "shareholder")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: shareholder:{symbol}")
                return cached

        try:
            response = await get_shareholder_data(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "shareholder", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for shareholder:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching shareholder for {symbol}: {e}")
            return None

    async def _fetch_margin(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取融资融券数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "margin")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: margin:{symbol}")
                return cached

        try:
            response = await get_margin_data(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "margin", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for margin:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching margin for {symbol}: {e}")
            return None

    async def _fetch_peers(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取同业比较数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "peers")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: peers:{symbol}")
                return cached

        try:
            response = await get_peer_comparison(symbol)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "peers", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for peers:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching peers for {symbol}: {e}")
            return None

    async def _fetch_announcements(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """获取公司公告数据"""
        if use_cache:
            cached = self._get_from_cache(symbol, "announcements")
            if cached is not None:
                logger.debug(f"[F9Fetcher] Cache hit: announcements:{symbol}")
                return cached

        try:
            response = await get_announcements(symbol, page=1, page_size=20)
            data = self._extract_data(response)
            if data is not None and use_cache:
                self._set_to_cache(symbol, "announcements", data)
            return data
        except CircuitBreakerOpen:
            logger.warning(f"[F9Fetcher] Circuit breaker open for announcements:{symbol}")
            return None
        except Exception as e:
            logger.error(f"[F9Fetcher] Error fetching announcements for {symbol}: {e}")
            return None

    async def fetch(
        self,
        symbol: str,
        tabs: Optional[List[str]] = None,
        timeout: float = 10.0,
        use_cache: bool = True
    ) -> F9DataResult:
        """
        获取 F9 深度数据

        Args:
            symbol: 股票代码
            tabs: 要获取的数据 tabs，默认 ["financial", "institution", "forecast", "shareholder"]
            timeout: 单个 tab 超时时间（秒）
            use_cache: 是否使用缓存

        Returns:
            F9DataResult 对象
        """
        if tabs is None:
            tabs = DEFAULT_TABS

        # 标准化股票代码
        normalized_symbol = normalize_f9_symbol(symbol)

        result = F9DataResult(symbol=normalized_symbol, fetched_at=datetime.now())

        # 构建 fetch 任务映射
        fetchers = {
            "financial": self._fetch_financial,
            "institution": self._fetch_institution,
            "forecast": self._fetch_forecast,
            "shareholder": self._fetch_shareholder,
            "margin": self._fetch_margin,
            "peers": self._fetch_peers,
            "announcements": self._fetch_announcements,
        }

        # 并行获取所有请求的 tabs
        tasks = {}
        for tab in tabs:
            if tab in fetchers:
                tasks[tab] = asyncio.create_task(
                    asyncio.wait_for(fetchers[tab](normalized_symbol, use_cache), timeout=timeout)
                )

        if not tasks:
            result.error = f"No valid tabs specified: {tabs}"
            return result

        # 等待所有任务完成
        done, pending = await asyncio.wait(tasks.values(), return_when=asyncio.ALL_COMPLETED)

        # 收集结果
        errors = []
        for tab, task in tasks.items():
            try:
                data = task.result()
                if data is None:
                    errors.append(f"{tab}: data is None (possibly circuit breaker open)")
                else:
                    setattr(result, tab, data)
            except asyncio.TimeoutError:
                errors.append(f"{tab}: timeout after {timeout}s")
                logger.warning(f"[F9Fetcher] Timeout for {tab}:{normalized_symbol}")
            except CircuitBreakerOpen:
                errors.append(f"{tab}: circuit breaker open")
                logger.warning(f"[F9Fetcher] Circuit breaker open for {tab}:{normalized_symbol}")
            except Exception as e:
                errors.append(f"{tab}: {str(e)}")
                logger.error(f"[F9Fetcher] Error fetching {tab} for {normalized_symbol}: {e}")

        # 取消未完成的任务
        for task in pending:
            task.cancel()

        if errors:
            result.error = "; ".join(errors)

        return result


# 单例模式
_f9_fetcher_instance: Optional[F9Fetcher] = None
_f9_fetcher_lock = threading.Lock()


def get_f9_fetcher() -> F9Fetcher:
    """
    获取 F9Fetcher 单例实例

    使用双检查锁定模式确保线程安全
    """
    global _f9_fetcher_instance

    if _f9_fetcher_instance is None:
        with _f9_fetcher_lock:
            if _f9_fetcher_instance is None:
                _f9_fetcher_instance = F9Fetcher()

    return _f9_fetcher_instance
