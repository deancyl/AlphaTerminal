"""
数据源降级链配置

定义每种数据类型的完整降级链:
- 主数据源 → 备用数据源 → 本地缓存 → 静态fallback
"""
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DataType(Enum):
    """数据类型枚举"""
    KLINE = "kline"           # K线数据
    QUOTE = "quote"           # 实时行情
    FOREX = "forex"           # 外汇数据
    NEWS = "news"             # 新闻数据
    MACRO = "macro"           # 宏观数据
    SECTOR = "sector"         # 板块数据


@dataclass
class DegradationLevel:
    """降级级别"""
    source: str               # 数据源名称
    fetch_fn: Optional[Callable] = None  # 获取函数
    is_fallback: bool = False # 是否为fallback数据


class DegradationChain:
    """降级链管理器"""
    
    # 各数据类型的降级链配置
    CHAINS: Dict[DataType, List[str]] = {
        DataType.KLINE: ["akshare", "eastmoney", "sina", "cache"],
        DataType.QUOTE: ["sina", "tencent", "eastmoney", "cache"],
        DataType.FOREX: ["eastmoney", "cfets", "static"],
        DataType.NEWS: ["eastmoney", "sina", "cache"],
        DataType.MACRO: ["akshare", "eastmoney", "cache"],
        DataType.SECTOR: ["eastmoney", "sina", "cache"],
    }
    
    # Fallback数据标记
    FALLBACK_SOURCES = {"static", "cache"}
    
    def __init__(self):
        self._current_level: Dict[DataType, int] = {}
    
    def get_sources(self, data_type: DataType) -> List[str]:
        """获取降级链"""
        return self.CHAINS.get(data_type, [])
    
    def get_current_source(self, data_type: DataType) -> str:
        """获取当前使用的数据源"""
        level = self._current_level.get(data_type, 0)
        sources = self.get_sources(data_type)
        return sources[level] if level < len(sources) else sources[-1]
    
    def degrade(self, data_type: DataType) -> Optional[str]:
        """降级到下一级"""
        sources = self.get_sources(data_type)
        current = self._current_level.get(data_type, 0)
        
        if current < len(sources) - 1:
            self._current_level[data_type] = current + 1
            new_source = sources[current + 1]
            logger.warning(f"[DegradationChain] {data_type.value} 降级: {sources[current]} → {new_source}")
            return new_source
        return None
    
    def recover(self, data_type: DataType):
        """恢复到主数据源"""
        self._current_level[data_type] = 0
        logger.info(f"[DegradationChain] {data_type.value} 恢复到主数据源")
    
    def is_fallback(self, source: str) -> bool:
        """判断是否为fallback数据"""
        return source in self.FALLBACK_SOURCES
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            data_type.value: {
                "current_source": self.get_current_source(data_type),
                "level": self._current_level.get(data_type, 0),
                "chain": self.get_sources(data_type)
            }
            for data_type in DataType
        }


# 全局实例
_chain: Optional[DegradationChain] = None


def get_degradation_chain() -> DegradationChain:
    """获取降级链单例"""
    global _chain
    if _chain is None:
        _chain = DegradationChain()
    return _chain
