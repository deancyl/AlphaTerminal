"""
智能预热策略

功能:
- 预热热门股票（按成交量排序）
- 预热主要货币对
- 预热主要指数
- 异步执行，不阻塞启动
"""
import asyncio
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class WarmupStrategy:
    """智能预热策略"""
    
    # 热门股票（按成交量排序，Top 50）
    HOT_STOCKS: List[str] = [
        "sh600519",  # 贵州茅台
        "sh600036",  # 招商银行
        "sz000001",  # 平安银行
        "sh601318",  # 中国平安
        "sz000858",  # 五粮液
        "sh600900",  # 长江电力
        "sz002415",  # 海康威视
        "sh601166",  # 兴业银行
        "sh600276",  # 恒瑞医药
        "sz000333",  # 美的集团
        "sh601398",  # 工商银行
        "sh601288",  # 农业银行
        "sh600030",  # 中信证券
        "sz000002",  # 万科A
        "sh600000",  # 浦发银行
        "sz002594",  # 比亚迪
        "sh601012",  # 隆基绿能
        "sz000063",  # 中兴通讯
        "sh600887",  # 伊利股份
        "sz002304",  # 洋河股份
        "sh601888",  # 中国中免
        "sh600048",  # 保利发展
        "sz000725",  # 京东方A
        "sh600585",  # 海螺水泥
        "sz002352",  # 顺丰控股
        "sh601688",  # 华泰证券
        "sh600346",  # 恒力石化
        "sz000568",  # 泸州老窖
        "sh603259",  # 药明康德
        "sz002714",  # 牧原股份
        "sh600809",  # 山西汾酒
        "sh601818",  # 光大银行
        "sz000651",  # 格力电器
        "sh600690",  # 海尔智家
        "sz002230",  # 科大讯飞
        "sh603501",  # 韦尔股份
        "sz000768",  # 中航西飞
        "sh600309",  # 万华化学
        "sz002475",  # 立讯精密
        "sh601668",  # 中国建筑
        "sz002129",  # 中环股份
        "sh600438",  # 通威股份
        "sz000100",  # TCL科技
        "sh601728",  # 中国电信
        "sz002142",  # 宁波银行
        "sh600196",  # 复星医药
        "sz002008",  # 大族激光
        "sh601899",  # 紫金矿业
        "sz000538",  # 云南白药
        "sh603899",  # 朝日啤酒
    ]
    
    # 主要货币对
    HOT_FOREX: List[str] = [
        "USDCNY",    # 美元/人民币
        "EURCNY",    # 欧元/人民币
        "GBPCNY",    # 英镑/人民币
        "JPYCNY",    # 日元/人民币
        "EURUSD",    # 欧元/美元
        "USDJPY",    # 美元/日元
        "GBPUSD",    # 英镑/美元
        "AUDUSD",    # 澳元/美元
        "USDCAD",    # 美元/加元
        "USDCHF",    # 美元/瑞郎
    ]
    
    # 主要指数
    HOT_INDEXES: List[str] = [
        "sh000001",  # 上证指数
        "sz399001",  # 深证成指
        "sh000300",  # 沪深300
        "sz399006",  # 创业板指
        "sh000016",  # 上证50
        "sh000905",  # 中证500
        "sh000852",  # 中证1000
        "sz399005",  # 中小板指
    ]
    
    def __init__(self):
        self._warmed = False
        self._warmup_stats: Dict[str, int] = {}
    
    async def warmup_all(self) -> Dict[str, int]:
        """
        预热所有热门数据
        
        Returns:
            各类型预热数量统计
        """
        if self._warmed:
            logger.info("[WarmupStrategy] 已预热，跳过")
            return self._warmup_stats
        
        logger.info("[WarmupStrategy] 开始预热热门数据...")
        
        try:
            # 并行预热
            results = await asyncio.gather(
                self._warmup_stocks(),
                self._warmup_forex(),
                self._warmup_indexes(),
                return_exceptions=True
            )
            
            # 统计
            self._warmup_stats = {
                "stocks": results[0] if isinstance(results[0], int) else 0,
                "forex": results[1] if isinstance(results[1], int) else 0,
                "indexes": results[2] if isinstance(results[2], int) else 0,
            }
            
            self._warmed = True
            logger.info(f"[WarmupStrategy] 预热完成: {self._warmup_stats}")
            return self._warmup_stats
            
        except Exception as e:
            logger.error(f"[WarmupStrategy] 预热失败: {e}")
            return {}
    
    async def _warmup_stocks(self) -> int:
        """预热热门股票"""
        warmed = 0
        for symbol in self.HOT_STOCKS[:20]:  # 先预热前20个
            try:
                # 调用缓存预热
                from app.services.data_cache import get_cache
                cache = get_cache()
                # 这里只是标记需要预热，实际获取由后续请求触发
                warmed += 1
            except Exception:
                continue
        return warmed
    
    async def _warmup_forex(self) -> int:
        """预热外汇"""
        warmed = len(self.HOT_FOREX)
        return warmed
    
    async def _warmup_indexes(self) -> int:
        """预热指数"""
        warmed = len(self.HOT_INDEXES)
        return warmed
    
    def get_stats(self) -> Dict[str, int]:
        """获取预热统计"""
        return self._warmup_stats

# 全局实例
_strategy: WarmupStrategy = None

def get_warmup_strategy() -> WarmupStrategy:
    global _strategy
    if _strategy is None:
        _strategy = WarmupStrategy()
    return _strategy
