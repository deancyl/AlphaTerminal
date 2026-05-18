"""
MacroDataFetcher - Copilot 宏观数据获取器

功能特性:
- 使用 BFF 端点高效获取所有宏观数据
- 直接调用路由函数（非 HTTP 调用）
- 5 分钟缓存 TTL
- 单例模式（线程安全）
- 超时保护

设计原则:
- 优先使用 BFF 端点（单次调用获取所有数据）
- 支持按需获取单个指标
- 使用 DataCache 单例进行缓存
"""

import logging
import threading
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.data_cache import get_cache
from app.routers import macro as macro_router

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构定义
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MacroDataResult:
    """宏观数据结果"""
    indicators: Dict[str, Any]  # {gdp: {...}, cpi: {...}, ...}
    overview: Optional[Dict[str, Any]] = None
    calendar: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now()


# ─────────────────────────────────────────────────────────────────────────────
# MacroFetcher 类
# ─────────────────────────────────────────────────────────────────────────────

class MacroFetcher:
    """
    宏观数据获取器
    
    特性:
    - 使用 BFF 端点 get_macro_dashboard() 高效获取数据
    - 直接调用路由函数（非 HTTP 调用）
    - 5 分钟缓存 TTL
    """
    
    CACHE_TTL = 300  # 5 分钟缓存
    DEFAULT_TIMEOUT = 15.0  # 默认超时时间
    
    # 支持的指标列表
    SUPPORTED_INDICATORS = ['gdp', 'cpi', 'ppi', 'pmi', 'm2', 'social_financing', 
                           'industrial_production', 'unemployment']
    
    def __init__(self):
        """初始化获取器"""
        self._cache = get_cache()
        logger.info("[MacroFetcher] 初始化完成")
    
    async def fetch(
        self,
        indicators: Optional[List[str]] = None,
        use_bff: bool = True,
        timeout: Optional[float] = None
    ) -> MacroDataResult:
        """
        获取宏观数据
        
        Args:
            indicators: 指标列表，None 表示获取所有指标
            use_bff: 是否使用 BFF 端点（默认 True，推荐）
            timeout: 超时时间（秒），None 使用默认值
            
        Returns:
            MacroDataResult 对象
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        
        # 默认获取所有指标
        if indicators is None:
            indicators = self.SUPPORTED_INDICATORS
        
        # 验证指标
        invalid = [i for i in indicators if i not in self.SUPPORTED_INDICATORS]
        if invalid:
            logger.warning(f"[MacroFetcher] 无效指标: {invalid}")
            indicators = [i for i in indicators if i in self.SUPPORTED_INDICATORS]
        
        try:
            if use_bff:
                # 使用 BFF 端点（推荐）
                return await self._fetch_bff(timeout)
            else:
                # 按需获取单个指标
                return await self._fetch_individual(indicators, timeout)
                
        except asyncio.TimeoutError:
            logger.error(f"[MacroFetcher] 获取超时 ({timeout}s)")
            return MacroDataResult(
                indicators={},
                error=f"数据获取超时 ({timeout}秒)"
            )
        except Exception as e:
            logger.error(f"[MacroFetcher] 获取失败: {e}")
            return MacroDataResult(
                indicators={},
                error=f"数据获取失败: {str(e)}"
            )
    
    async def _fetch_bff(self, timeout: float) -> MacroDataResult:
        """
        使用 BFF 端点获取所有数据
        
        直接调用路由函数 get_macro_dashboard()
        """
        cache_key = "copilot:macro:bff"
        
        # 检查缓存
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug("[MacroFetcher] 缓存命中: BFF")
            return MacroDataResult(
                indicators=cached.get('indicators', {}),
                overview=cached.get('overview'),
                calendar=cached.get('calendar'),
                fetched_at=datetime.now()
            )
        
        # 调用路由函数（直接调用，非 HTTP）
        try:
            # 使用 asyncio.wait_for 添加超时保护
            response = await asyncio.wait_for(
                macro_router.get_macro_dashboard(),
                timeout=timeout
            )
            
            # 解析响应
            response_body = getattr(response, 'body', None)
            if response_body is not None:
                # FastAPI Response 对象
                import json
                data = json.loads(response_body.decode())
            elif isinstance(response, dict):
                data = response
            else:
                data = response
            
            # 提取数据
            result_data = data.get('data', data)
            
            result = MacroDataResult(
                indicators={
                    'gdp': result_data.get('gdp', {}),
                    'cpi': result_data.get('cpi', {}),
                    'ppi': result_data.get('ppi', {}),
                    'pmi': result_data.get('pmi', {}),
                    'm2': result_data.get('m2', {}),
                    'social_financing': result_data.get('social_financing', {}),
                    'industrial_production': result_data.get('industrial_production', {}),
                    'unemployment': result_data.get('unemployment', {}),
                },
                overview=result_data.get('overview'),
                calendar=result_data.get('calendar', []),
                fetched_at=datetime.now()
            )
            
            # 缓存结果
            cache_data = {
                'indicators': result.indicators,
                'overview': result.overview,
                'calendar': result.calendar,
            }
            self._cache.set(cache_key, cache_data, ttl=self.CACHE_TTL)
            
            logger.info("[MacroFetcher] BFF 获取成功")
            return result
            
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"[MacroFetcher] BFF 调用失败: {e}")
            raise
    
    async def _fetch_individual(
        self,
        indicators: List[str],
        timeout: float
    ) -> MacroDataResult:
        """
        按需获取单个指标
        
        直接调用对应的路由函数
        """
        result_data = {}
        
        # 指标到路由函数的映射
        indicator_funcs = {
            'gdp': lambda: macro_router.get_gdp_data(limit=12),
            'cpi': lambda: macro_router.get_cpi_data(limit=12),
            'ppi': lambda: macro_router.get_ppi_data(limit=12),
            'pmi': lambda: macro_router.get_pmi_data(limit=12),
            'm2': lambda: macro_router.get_m2_data(limit=12),
        }
        
        for indicator in indicators:
            if indicator not in indicator_funcs:
                continue
            
            cache_key = f"copilot:macro:{indicator}"
            
            # 检查缓存
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug(f"[MacroFetcher] 缓存命中: {indicator}")
                result_data[indicator] = cached
                continue
            
            try:
                # 调用路由函数
                response = await asyncio.wait_for(
                    indicator_funcs[indicator](),
                    timeout=timeout
                )
                
                # 解析响应
                response_body = getattr(response, 'body', None)
                if response_body is not None:
                    import json
                    data = json.loads(response_body.decode())
                elif isinstance(response, dict):
                    data = response
                else:
                    data = response
                
                indicator_data = data.get('data', data)
                result_data[indicator] = indicator_data
                
                # 缓存
                self._cache.set(cache_key, indicator_data, ttl=self.CACHE_TTL)
                
                logger.debug(f"[MacroFetcher] 获取成功: {indicator}")
                
            except asyncio.TimeoutError:
                logger.warning(f"[MacroFetcher] 超时: {indicator}")
                result_data[indicator] = {'error': 'timeout'}
            except Exception as e:
                logger.warning(f"[MacroFetcher] 获取失败: {indicator}, {e}")
                result_data[indicator] = {'error': str(e)}
        
        return MacroDataResult(
            indicators=result_data,
            fetched_at=datetime.now()
        )
    
    def get_supported_indicators(self) -> List[str]:
        """获取支持的指标列表"""
        return self.SUPPORTED_INDICATORS.copy()
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.delete("copilot:macro:bff")
        for indicator in self.SUPPORTED_INDICATORS:
            self._cache.delete(f"copilot:macro:{indicator}")
        logger.info("[MacroFetcher] 缓存已清空")


# ─────────────────────────────────────────────────────────────────────────────
# 单例模式（双重检查锁定）
# ─────────────────────────────────────────────────────────────────────────────

_macro_fetcher_instance: Optional[MacroFetcher] = None
_macro_fetcher_lock = threading.Lock()


def get_macro_fetcher() -> MacroFetcher:
    """
    获取 MacroFetcher 单例实例
    
    使用双重检查锁定模式确保线程安全
    """
    global _macro_fetcher_instance
    
    if _macro_fetcher_instance is None:
        with _macro_fetcher_lock:
            if _macro_fetcher_instance is None:
                _macro_fetcher_instance = MacroFetcher()
    
    return _macro_fetcher_instance
