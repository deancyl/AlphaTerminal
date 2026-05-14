"""
Fetcher Priority Configuration — 数据源优先级配置

用于定义不同数据类型的获取优先级，支持动态降级和路由。

默认优先级：
- history: AkShare → EastMoney → Sina（历史数据优先 AkShare）
- realtime: Sina → Tencent → EastMoney（实时数据优先 Sina）
- fund_nav: AkShare → EastMoney（基金净值优先 AkShare）
"""
from pydantic import BaseModel
from typing import Dict, List, Optional

from app.db.database import get_admin_config, set_admin_config


class FetcherPriority(BaseModel):
    """数据源优先级配置"""
    
    history: List[str] = ["akshare", "eastmoney", "sina"]
    realtime: List[str] = ["sina", "tencent", "eastmoney"]
    fund_nav: List[str] = ["akshare", "eastmoney"]
    futures: List[str] = ["akshare", "sina"]
    hk_stocks: List[str] = ["tencent"]
    us_stocks: List[str] = ["alphavantage"]
    
    def get_sources(self, data_type: str) -> List[str]:
        """获取指定数据类型的优先级列表"""
        return getattr(self, data_type, ["sina"])


class FetcherPriorityConfig:
    """优先级配置管理器"""
    
    CONFIG_KEY = "fetcher_priority"
    
    @classmethod
    def load(cls) -> FetcherPriority:
        """从数据库加载配置，不存在则使用默认值"""
        config = get_admin_config(cls.CONFIG_KEY, {})
        return FetcherPriority(**config)
    
    @classmethod
    def save(cls, priority: FetcherPriority):
        """保存配置到数据库"""
        set_admin_config(cls.CONFIG_KEY, priority.model_dump())
    
    @classmethod
    def reset(cls) -> FetcherPriority:
        """重置为默认配置"""
        default = FetcherPriority()
        cls.save(default)
        return default


# 全局默认配置实例
_default_priority: Optional[FetcherPriority] = None


def get_fetcher_priority() -> FetcherPriority:
    """获取当前优先级配置"""
    global _default_priority
    if _default_priority is None:
        _default_priority = FetcherPriorityConfig.load()
    return _default_priority


def set_fetcher_priority(priority: FetcherPriority):
    """更新优先级配置"""
    global _default_priority
    _default_priority = priority
    FetcherPriorityConfig.save(priority)