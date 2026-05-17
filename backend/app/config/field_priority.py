"""
字段级数据源优先级配置

解决问题：
- 不同数据源对同一字段可能返回不同值
- 需要定义每个字段的数据源优先级

设计原则：
- 价格相关：优先mootdx/sina（更实时）
- 估值相关：优先tencent/eastmoney（更准确）
- 成交量：优先sina（更稳定）
"""

from pydantic import BaseModel
from typing import List


class FieldPriority(BaseModel):
    """字段级数据源优先级配置"""
    
    # ========== 价格相关字段 ==========
    # 优先mootdx（更实时），其次sina，最后tencent
    price: List[str] = ["mootdx", "sina", "tencent", "eastmoney"]
    open: List[str] = ["mootdx", "sina", "tencent", "eastmoney"]
    high: List[str] = ["mootdx", "sina", "tencent", "eastmoney"]
    low: List[str] = ["mootdx", "sina", "tencent", "eastmoney"]
    prev_close: List[str] = ["mootdx", "sina", "tencent", "eastmoney"]
    
    # ========== 估值相关字段 ==========
    # 优先tencent（更准确），其次eastmoney
    pe_ttm: List[str] = ["tencent", "eastmoney", "mootdx"]
    pe_lyr: List[str] = ["tencent", "eastmoney"]
    pb: List[str] = ["tencent", "eastmoney", "mootdx"]
    ps: List[str] = ["tencent", "eastmoney"]
    total_mv: List[str] = ["tencent", "eastmoney"]
    circ_mv: List[str] = ["tencent", "eastmoney"]
    
    # ========== 成交量相关字段 ==========
    # 优先sina（更稳定）
    volume: List[str] = ["sina", "mootdx", "tencent", "eastmoney"]
    amount: List[str] = ["sina", "mootdx", "tencent", "eastmoney"]
    turnover: List[str] = ["sina", "tencent", "eastmoney"]
    
    # ========== 涨跌幅字段 ==========
    # 优先eastmoney（更准确）
    change_pct: List[str] = ["eastmoney", "sina", "tencent", "mootdx"]
    chg: List[str] = ["eastmoney", "sina", "tencent", "mootdx"]
    chg_pct: List[str] = ["eastmoney", "sina", "tencent", "mootdx"]
    
    # ========== 其他字段 ==========
    amplitude: List[str] = ["eastmoney", "sina", "tencent"]
    turnover_rate: List[str] = ["eastmoney", "sina", "tencent"]
    
    def get_priority(self, field: str) -> List[str]:
        """
        获取指定字段的优先级列表
        
        Args:
            field: 字段名
            
        Returns:
            数据源优先级列表
        """
        return getattr(self, field, ["sina", "tencent", "eastmoney"])
    
    def get_all_fields(self) -> List[str]:
        """获取所有已配置的字段名"""
        return [
            'price', 'open', 'high', 'low', 'prev_close',
            'pe_ttm', 'pe_lyr', 'pb', 'ps', 'total_mv', 'circ_mv',
            'volume', 'amount', 'turnover',
            'change_pct', 'chg', 'chg_pct',
            'amplitude', 'turnover_rate'
        ]


# 全局配置实例
field_priority = FieldPriority()
