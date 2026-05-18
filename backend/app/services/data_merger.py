"""
数据源合并器

功能：
- 并行从多个数据源获取数据
- 按字段优先级合并数据
- 记录数据源冲突日志

设计原则：
- 使用asyncio.gather实现并行请求
- 字段级优先级合并（非整体降级）
- 冲突时记录日志，便于排查
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from app.config.field_priority import field_priority

logger = logging.getLogger(__name__)


class DataMerger:
    """多数据源合并器"""
    
    def __init__(self, fetchers: Dict[str, Any]):
        """
        初始化合并器
        
        Args:
            fetchers: 数据源获取器字典 {'sina': SinaFetcher, 'tencent': TencentFetcher, ...}
        """
        self.fetchers = fetchers
    
    async def fetch_and_merge(self, symbol: str, fields: List[str] = None) -> Dict[str, Any]:
        """
        并行从多个数据源获取数据，按字段优先级合并
        
        Args:
            symbol: 股票代码
            fields: 需要获取的字段列表，None表示获取所有字段
            
        Returns:
            合并后的数据字典
        """
        if not self.fetchers:
            raise ValueError("No fetchers available")
        
        # 并行请求所有数据源
        source_names = list(self.fetchers.keys())
        tasks = [
            self._safe_fetch(name, fetcher, symbol)
            for name, fetcher in self.fetchers.items()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 构建源数据字典
        source_data = {}
        for name, result in zip(source_names, results):
            if isinstance(result, Exception):
                logger.warning(f"[DataMerger] {name} fetch failed: {result}")
            elif result:
                source_data[name] = result
        
        if not source_data:
            raise ValueError(f"All sources failed for {symbol}")
        
        # 按字段优先级合并
        merged = self._merge_by_priority(source_data, fields)
        merged['_sources'] = list(source_data.keys())
        
        return merged
    
    async def _safe_fetch(self, name: str, fetcher: Any, symbol: str) -> Optional[Dict]:
        """
        安全获取数据（捕获异常）
        
        Args:
            name: 数据源名称
            fetcher: 数据源获取器
            symbol: 股票代码
            
        Returns:
            数据字典或None
        """
        try:
            # 支持同步和异步获取器
            if asyncio.iscoroutinefunction(fetcher.get_quote):
                result = await fetcher.get_quote(symbol)
            else:
                result = await asyncio.to_thread(fetcher.get_quote, symbol)
            
            if result:
                logger.debug(f"[DataMerger] {name} fetched {symbol}: {len(result)} fields")
            return result
            
        except Exception as e:
            logger.debug(f"[DataMerger] {name} error: {e}")
            return None
    
    def _merge_by_priority(self, source_data: Dict[str, Dict], fields: List[str] = None) -> Dict[str, Any]:
        """
        按字段优先级合并数据
        
        Args:
            source_data: 源数据字典 {'sina': {...}, 'tencent': {...}, ...}
            fields: 需要合并的字段列表，None表示合并所有字段
            
        Returns:
            合并后的数据字典
        """
        merged = {}
        
        # 确定需要合并的字段
        if fields is None:
            all_fields = set()
            for data in source_data.values():
                all_fields.update(data.keys())
            fields = list(all_fields)
        
        # 对每个字段，按优先级选择值
        conflicts = []
        
        for field in fields:
            if field.startswith('_'):  # 跳过内部字段
                continue
                
            priorities = field_priority.get_priority(field)
            selected_value = None
            selected_source = None
            
            for source in priorities:
                if source in source_data and field in source_data[source]:
                    selected_value = source_data[source][field]
                    selected_source = source
                    break
            
            if selected_value is not None:
                merged[field] = selected_value
                merged[f'_source_{field}'] = selected_source
            
            # 检测冲突：多个数据源都有该字段但值不同
            values = {}
            for source, data in source_data.items():
                if field in data and data[field] is not None:
                    values[source] = data[field]
            
            if len(values) > 1:
                unique_values = set(str(v) for v in values.values())
                if len(unique_values) > 1:
                    conflicts.append({
                        'field': field,
                        'values': values,
                        'selected': selected_source
                    })
        
        # 记录冲突日志
        if conflicts:
            for conflict in conflicts:
                logger.info(
                    f"[DataMerger] Field conflict: {conflict['field']}, "
                    f"values={conflict['values']}, selected={conflict['selected']}"
                )
        
        return merged
    
    def get_available_sources(self) -> List[str]:
        """获取可用的数据源列表"""
        return list(self.fetchers.keys())


# 辅助函数：创建默认合并器
def create_default_merger():
    """
    创建默认的数据源合并器
    
    Returns:
        DataMerger实例
    """
    from app.services.fetchers.sina import SinaFetcher
    from app.services.fetchers.tencent import TencentFetcher
    from app.services.fetchers.eastmoney import EastmoneyFetcher
    
    fetchers = {
        'sina': SinaFetcher(),
        'tencent': TencentFetcher(),
        'eastmoney': EastmoneyFetcher(),
    }
    
    return DataMerger(fetchers)
