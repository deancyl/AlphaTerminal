"""
统一数据获取抽象层

整合所有数据源获取逻辑，提供统一接口。

功能特性:
- 缓存优先策略
- 熔断器保护
- 降级数据源切换
- 延迟统计
- 错误处理

使用方式:
    from app.services.unified_fetcher import get_fetcher, DataSource
    
    fetcher = get_fetcher()
    
    result = await fetcher.fetch(
        key="kline:sh600519:daily",
        fetch_fn=lambda: akshare.stock_zh_a_hist(...),
        ttl=300,
        source=DataSource.AKSHARE,
        fallback_fn=lambda: sina_finance.get_kline(...)
    )
    
    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Data: {result.data}")
"""

import asyncio
import time
import logging
from typing import Any, Callable, Optional, Dict, Awaitable, Union
from dataclasses import dataclass
from enum import Enum

from app.services.data_cache import get_cache
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from app.services.cache_metrics import get_cache_metrics

logger = logging.getLogger(__name__)


class DataSource(Enum):
    """数据源枚举"""
    AKSHARE = "akshare"
    SINA = "sina"
    TENCENT = "tencent"
    EASTMONEY = "eastmoney"
    QLIB = "qlib"
    CUSTOM = "custom"


@dataclass
class FetchResult:
    """数据获取结果"""
    data: Any
    source: DataSource
    latency_ms: float
    from_cache: bool
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """是否成功获取数据"""
        return self.error is None


class UnifiedFetcher:
    """
    统一数据获取器
    
    整合所有数据源获取逻辑，提供统一的缓存、熔断、降级机制。
    
    特性:
    - 缓存优先: 先查缓存，命中则直接返回
    - 熔断保护: 每个数据源独立熔断器，防止级联故障
    - 降级切换: 主数据源失败时自动切换到降级数据源
    - 延迟统计: 记录每次请求的延迟，用于监控
    """
    
    def __init__(self):
        self.cache = get_cache()
        self.metrics = get_cache_metrics()
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, source: DataSource) -> CircuitBreaker:
        """
        获取或创建数据源熔断器
        
        Args:
            source: 数据源枚举值
            
        Returns:
            该数据源的熔断器实例
        """
        if source.value not in self.breakers:
            self.breakers[source.value] = CircuitBreaker(
                name=source.value,
                failure_threshold=5,
                timeout=30.0
            )
        return self.breakers[source.value]
    
    async def fetch(
        self,
        key: str,
        fetch_fn: Union[Callable[[], Any], Callable[[], Awaitable[Any]]],
        ttl: Optional[int] = None,
        source: DataSource = DataSource.AKSHARE,
        fallback_fn: Optional[Union[Callable[[], Any], Callable[[], Awaitable[Any]]]] = None
    ) -> FetchResult:
        """
        统一数据获取方法
        
        流程:
        1. 尝试缓存
        2. 尝试主数据源（带熔断器）
        3. 尝试降级数据源
        4. 返回结果
        
        Args:
            key: 缓存键
            fetch_fn: 数据获取函数（同步或异步）
            ttl: 缓存过期时间（秒）
            source: 主数据源
            fallback_fn: 降级数据源函数
            
        Returns:
            FetchResult 对象
        """
        start_time = time.time()
        
        # 1. 尝试缓存
        cached = self.cache.get(key)
        if cached is not None:
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.record_hit()
            return FetchResult(
                data=cached,
                source=source,
                latency_ms=latency_ms,
                from_cache=True
            )
        
        self.metrics.record_miss()
        
        # 2. 尝试主数据源（带熔断器）
        breaker = self.get_breaker(source)
        
        try:
            if breaker.is_available():
                with breaker:
                    data = await self._execute_fetch(fetch_fn)
                    
                    # 写入缓存
                    self.cache.set(key, data, ttl)
                    
                    latency_ms = (time.time() - start_time) * 1000
                    self.metrics.record_latency(source.value, latency_ms / 1000)
                    
                    return FetchResult(
                        data=data,
                        source=source,
                        latency_ms=latency_ms,
                        from_cache=False
                    )
        except CircuitBreakerOpen as e:
            logger.warning(f"[UnifiedFetcher] 熔断器打开: {source.value}, {e}")
        except Exception as e:
            logger.error(f"[UnifiedFetcher] 主数据源失败: {source.value}, {e}")
            self.metrics.record_error(source.value)
        
        # 3. 尝试降级数据源
        if fallback_fn is not None:
            fallback_source = self._get_fallback_source(source)
            fallback_breaker = self.get_breaker(fallback_source)
            
            try:
                if fallback_breaker.is_available():
                    with fallback_breaker:
                        data = await self._execute_fetch(fallback_fn)
                        
                        # 写入缓存
                        self.cache.set(key, data, ttl)
                        
                        latency_ms = (time.time() - start_time) * 1000
                        self.metrics.record_latency(fallback_source.value, latency_ms / 1000)
                        
                        logger.info(f"[UnifiedFetcher] 降级数据源成功: {fallback_source.value}")
                        
                        return FetchResult(
                            data=data,
                            source=fallback_source,
                            latency_ms=latency_ms,
                            from_cache=False
                        )
            except CircuitBreakerOpen as e:
                logger.warning(f"[UnifiedFetcher] 降级熔断器打开: {fallback_source.value}, {e}")
            except Exception as e:
                logger.error(f"[UnifiedFetcher] 降级数据源失败: {fallback_source.value}, {e}")
                self.metrics.record_error(fallback_source.value)
        
        # 4. 所有数据源都失败
        latency_ms = (time.time() - start_time) * 1000
        return FetchResult(
            data=None,
            source=source,
            latency_ms=latency_ms,
            from_cache=False,
            error="所有数据源均不可用"
        )
    
    async def _execute_fetch(
        self, 
        fetch_fn: Union[Callable[[], Any], Callable[[], Awaitable[Any]]]
    ) -> Any:
        """
        执行获取函数（支持同步和异步）
        
        Args:
            fetch_fn: 数据获取函数
            
        Returns:
            获取的数据
        """
        if asyncio.iscoroutinefunction(fetch_fn):
            return await fetch_fn()
        else:
            # 同步函数在线程池中执行
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, fetch_fn)
    
    def _get_fallback_source(self, primary: DataSource) -> DataSource:
        """
        获取降级数据源
        
        Args:
            primary: 主数据源
            
        Returns:
            降级数据源
        """
        fallback_map = {
            DataSource.AKSHARE: DataSource.EASTMONEY,
            DataSource.SINA: DataSource.TENCENT,
            DataSource.TENCENT: DataSource.SINA,
            DataSource.EASTMONEY: DataSource.AKSHARE,
            DataSource.QLIB: DataSource.AKSHARE,
        }
        return fallback_map.get(primary, DataSource.CUSTOM)
    
    def fetch_sync(
        self,
        key: str,
        fetch_fn: Callable[[], Any],
        ttl: Optional[int] = None,
        source: DataSource = DataSource.AKSHARE,
        fallback_fn: Optional[Callable[[], Any]] = None
    ) -> FetchResult:
        """
        同步数据获取方法
        
        Args:
            key: 缓存键
            fetch_fn: 数据获取函数
            ttl: 缓存过期时间（秒）
            source: 主数据源
            fallback_fn: 降级数据源函数
            
        Returns:
            FetchResult 对象
        """
        start_time = time.time()
        
        # 1. 尝试缓存
        cached = self.cache.get(key)
        if cached is not None:
            latency_ms = (time.time() - start_time) * 1000
            self.metrics.record_hit()
            return FetchResult(
                data=cached,
                source=source,
                latency_ms=latency_ms,
                from_cache=True
            )
        
        self.metrics.record_miss()
        
        # 2. 尝试主数据源（带熔断器）
        breaker = self.get_breaker(source)
        
        try:
            if breaker.is_available():
                with breaker:
                    data = fetch_fn()
                    
                    # 写入缓存
                    self.cache.set(key, data, ttl)
                    
                    latency_ms = (time.time() - start_time) * 1000
                    self.metrics.record_latency(source.value, latency_ms / 1000)
                    
                    return FetchResult(
                        data=data,
                        source=source,
                        latency_ms=latency_ms,
                        from_cache=False
                    )
        except CircuitBreakerOpen as e:
            logger.warning(f"[UnifiedFetcher] 熔断器打开: {source.value}, {e}")
        except Exception as e:
            logger.error(f"[UnifiedFetcher] 主数据源失败: {source.value}, {e}")
            self.metrics.record_error(source.value)
        
        # 3. 尝试降级数据源
        if fallback_fn is not None:
            fallback_source = self._get_fallback_source(source)
            fallback_breaker = self.get_breaker(fallback_source)
            
            try:
                if fallback_breaker.is_available():
                    with fallback_breaker:
                        data = fallback_fn()
                        
                        # 写入缓存
                        self.cache.set(key, data, ttl)
                        
                        latency_ms = (time.time() - start_time) * 1000
                        self.metrics.record_latency(fallback_source.value, latency_ms / 1000)
                        
                        logger.info(f"[UnifiedFetcher] 降级数据源成功: {fallback_source.value}")
                        
                        return FetchResult(
                            data=data,
                            source=fallback_source,
                            latency_ms=latency_ms,
                            from_cache=False
                        )
            except CircuitBreakerOpen as e:
                logger.warning(f"[UnifiedFetcher] 降级熔断器打开: {fallback_source.value}, {e}")
            except Exception as e:
                logger.error(f"[UnifiedFetcher] 降级数据源失败: {fallback_source.value}, {e}")
                self.metrics.record_error(fallback_source.value)
        
        # 4. 所有数据源都失败
        latency_ms = (time.time() - start_time) * 1000
        return FetchResult(
            data=None,
            source=source,
            latency_ms=latency_ms,
            from_cache=False,
            error="所有数据源均不可用"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        stats = {
            "cache": self.cache.get_stats(),
            "breakers": {},
            "metrics": {
                "hit_rate": self.metrics.get_hit_rate(),
                "sources": {}
            }
        }
        
        for name, breaker in self.breakers.items():
            stats["breakers"][name] = breaker.get_stats()
            stats["metrics"]["sources"][name] = {
                "avg_latency": self.metrics.get_avg_latency(name),
                "p95_latency": self.metrics.get_p95_latency(name),
                "error_rate": self.metrics.get_error_rate(name)
            }
        
        return stats
    
    def reset_breaker(self, source: DataSource) -> bool:
        """
        重置指定数据源的熔断器
        
        Args:
            source: 数据源
            
        Returns:
            是否成功重置
        """
        if source.value in self.breakers:
            self.breakers[source.value].reset()
            logger.info(f"[UnifiedFetcher] 熔断器已重置: {source.value}")
            return True
        return False
    
    def reset_all_breakers(self) -> int:
        """
        重置所有熔断器
        
        Returns:
            重置的熔断器数量
        """
        count = 0
        for source in DataSource:
            if source.value in self.breakers:
                self.breakers[source.value].reset()
                count += 1
        logger.info(f"[UnifiedFetcher] 已重置 {count} 个熔断器")
        return count


# 全局实例
_fetcher: Optional[UnifiedFetcher] = None


def get_fetcher() -> UnifiedFetcher:
    """
    获取全局 UnifiedFetcher 实例（单例模式）
    
    Returns:
        UnifiedFetcher 实例
    """
    global _fetcher
    if _fetcher is None:
        _fetcher = UnifiedFetcher()
    return _fetcher
