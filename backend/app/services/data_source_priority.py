"""
数据源优先级配置

设计原则:
- 互补模式（Complementary）：不同数据源提供不同字段
- 字段级优先级：每个字段明确指定主数据源
- 故障降级：主数据源不可时，自动切换到备用源

数据源能力矩阵:
┌─────────────┬──────────────────────────────────────┐
│ 数据源       │ 字段                                  │
├─────────────┼──────────────────────────────────────┤
│ mootdx      │ price, open, high, low, volume,      │
│ (TCP, 11ms) │ bid1-5, ask1-5, ticks, financials    │
├─────────────┼──────────────────────────────────────┤
│ tencent     │ pe_ttm, pb, mcap, turnover,          │
│ (HTTP, 50ms)│ industry, concept                    │
├─────────────┼──────────────────────────────────────┤
│ sina        │ name, market, change_pct,            │
│ (HTTP, 30ms)│ amount                               │
├─────────────┼──────────────────────────────────────┤
│ akshare     │ financials, dividends, splits        │
│ (HTTP, 5s)  │                                      │
└─────────────┴──────────────────────────────────────┘
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass


class DataSource(str, Enum):
    """数据源枚举"""
    MOOTDX = "mootdx"      # 通达信TCP接口，11ms响应
    TENCENT = "tencent"    # 腾讯财经HTTP接口
    SINA = "sina"          # 新浪财经HTTP接口
    AKSHARE = "akshare"    # AkShare Python库


class DataMode(str, Enum):
    """数据获取模式"""
    COMPLEMENTARY = "complementary"  # 互补模式：不同源提供不同字段
    FAILOVER = "failover"            # 故障切换：主源失败时切换备用源
    PARALLEL = "parallel"            # 并行模式：同时请求多源，取最快响应


@dataclass
class FieldSource:
    """字段数据源配置"""
    primary: DataSource          # 主数据源
    fallback: Optional[DataSource] = None  # 备用数据源
    priority: int = 100          # 优先级（用于并行模式）
    

# ── 数据源优先级配置 ────────────────────────────────────────────────

DATA_SOURCE_PRIORITY: Dict[str, Dict[str, FieldSource]] = {
    
    # ── 行情数据（Quote）────────────────────────────────────────────
    "quote": {
        # 价格相关（mootdx优先，TCP协议不封IP）
        "price":      FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "open":       FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "high":       FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "low":        FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "close":      FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "volume":     FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "amount":     FieldSource(DataSource.SINA, DataSource.MOOTDX),
        
        # 盘口数据（mootdx独有）
        "bid1":       FieldSource(DataSource.MOOTDX),
        "bid1_vol":   FieldSource(DataSource.MOOTDX),
        "bid2":       FieldSource(DataSource.MOOTDX),
        "bid2_vol":   FieldSource(DataSource.MOOTDX),
        "bid3":       FieldSource(DataSource.MOOTDX),
        "bid3_vol":   FieldSource(DataSource.MOOTDX),
        "bid4":       FieldSource(DataSource.MOOTDX),
        "bid4_vol":   FieldSource(DataSource.MOOTDX),
        "bid5":       FieldSource(DataSource.MOOTDX),
        "bid5_vol":   FieldSource(DataSource.MOOTDX),
        "ask1":       FieldSource(DataSource.MOOTDX),
        "ask1_vol":   FieldSource(DataSource.MOOTDX),
        "ask2":       FieldSource(DataSource.MOOTDX),
        "ask2_vol":   FieldSource(DataSource.MOOTDX),
        "ask3":       FieldSource(DataSource.MOOTDX),
        "ask3_vol":   FieldSource(DataSource.MOOTDX),
        "ask4":       FieldSource(DataSource.MOOTDX),
        "ask4_vol":   FieldSource(DataSource.MOOTDX),
        "ask5":       FieldSource(DataSource.MOOTDX),
        "ask5_vol":   FieldSource(DataSource.MOOTDX),
        
        # 估值指标（腾讯优先，数据更全）
        "pe_ttm":     FieldSource(DataSource.TENCENT, DataSource.SINA),
        "pb":         FieldSource(DataSource.TENCENT, DataSource.SINA),
        "mcap":       FieldSource(DataSource.TENCENT),
        "turnover":   FieldSource(DataSource.TENCENT, DataSource.SINA),
        
        # 基本信息（新浪优先，响应快）
        "name":       FieldSource(DataSource.SINA, DataSource.TENCENT),
        "market":     FieldSource(DataSource.SINA),
        "change_pct": FieldSource(DataSource.SINA, DataSource.MOOTDX),
        
        # 分笔成交（mootdx独有）
        "ticks":      FieldSource(DataSource.MOOTDX),
    },
    
    # ── K线数据（History）────────────────────────────────────────────
    "kline": {
        "date":       FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "open":       FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "high":       FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "low":        FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "close":      FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "volume":     FieldSource(DataSource.MOOTDX, DataSource.SINA),
        "amount":     FieldSource(DataSource.SINA, DataSource.MOOTDX),
    },
    
    # ── 财务数据（Financials）────────────────────────────────────────
    "financials": {
        "revenue":    FieldSource(DataSource.MOOTDX, DataSource.AKSHARE),
        "profit":     FieldSource(DataSource.MOOTDX, DataSource.AKSHARE),
        "eps":        FieldSource(DataSource.MOOTDX, DataSource.AKSHARE),
        "roe":        FieldSource(DataSource.MOOTDX, DataSource.AKSHARE),
        "dividend":   FieldSource(DataSource.AKSHARE, DataSource.MOOTDX),
        "split":      FieldSource(DataSource.AKSHARE, DataSource.MOOTDX),
    },
    
    # ── 板块数据（Sector）────────────────────────────────────────────
    "sector": {
        "industry":   FieldSource(DataSource.TENCENT, DataSource.SINA),
        "concept":    FieldSource(DataSource.TENCENT, DataSource.SINA),
    },
}


# ── 数据源性能指标 ────────────────────────────────────────────────

DATA_SOURCE_PERFORMANCE = {
    DataSource.MOOTDX: {
        "latency_ms": 11,
        "protocol": "TCP",
        "rate_limit": "无限制",
        "features": ["price", "ticks", "financials", "dividends"],
    },
    DataSource.TENCENT: {
        "latency_ms": 50,
        "protocol": "HTTP",
        "rate_limit": "未知",
        "features": ["pe_ttm", "pb", "mcap", "industry", "concept"],
    },
    DataSource.SINA: {
        "latency_ms": 30,
        "protocol": "HTTP",
        "rate_limit": "未知",
        "features": ["price", "volume", "name", "market"],
    },
    DataSource.AKSHARE: {
        "latency_ms": 5000,
        "protocol": "HTTP",
        "rate_limit": "未知",
        "features": ["financials", "dividends", "splits"],
    },
}


# ── 辅助函数 ────────────────────────────────────────────────────────

def get_primary_source(data_type: str, field: str) -> Optional[DataSource]:
    """
    获取字段的主数据源
    
    Args:
        data_type: 数据类型 (quote, kline, financials, sector)
        field: 字段名
    
    Returns:
        主数据源枚举值，如果未配置则返回 None
    """
    if data_type not in DATA_SOURCE_PRIORITY:
        return None
    
    field_config = DATA_SOURCE_PRIORITY[data_type].get(field)
    return field_config.primary if field_config else None


def get_fallback_source(data_type: str, field: str) -> Optional[DataSource]:
    """
    获取字段的备用数据源
    
    Args:
        data_type: 数据类型
        field: 字段名
    
    Returns:
        备用数据源枚举值，如果未配置则返回 None
    """
    if data_type not in DATA_SOURCE_PRIORITY:
        return None
    
    field_config = DATA_SOURCE_PRIORITY[data_type].get(field)
    return field_config.fallback if field_config else None


def get_fields_by_source(data_type: str, source: DataSource) -> List[str]:
    """
    获取指定数据源提供的所有字段
    
    Args:
        data_type: 数据类型
        source: 数据源
    
    Returns:
        字段名列表
    """
    if data_type not in DATA_SOURCE_PRIORITY:
        return []
    
    fields = []
    for field, config in DATA_SOURCE_PRIORITY[data_type].items():
        if config.primary == source or config.fallback == source:
            fields.append(field)
    
    return fields


def should_use_complementary_mode(data_type: str) -> bool:
    """
    判断是否应该使用互补模式
    
    互补模式：不同数据源提供不同字段，需要合并
    故障切换模式：主源失败时切换备用源
    
    Args:
        data_type: 数据类型
    
    Returns:
        True 表示使用互补模式
    """
    # quote 和 kline 使用互补模式
    return data_type in ("quote", "kline")


# ── 示例用法 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    # 示例1：获取 price 字段的主数据源
    primary = get_primary_source("quote", "price")
    print(f"price 主数据源: {primary}")  # 输出: mootdx
    
    # 示例2：获取 pe_ttm 字段的备用数据源
    fallback = get_fallback_source("quote", "pe_ttm")
    print(f"pe_ttm 备用数据源: {fallback}")  # 输出: sina
    
    # 示例3：获取 mootdx 提供的所有字段
    fields = get_fields_by_source("quote", DataSource.MOOTDX)
    print(f"mootdx 提供的字段: {fields}")
    # 输出: ['price', 'open', 'high', 'low', 'close', 'volume', 'bid1', ...]
    
    # 示例4：判断是否使用互补模式
    mode = should_use_complementary_mode("quote")
    print(f"quote 使用互补模式: {mode}")  # 输出: True
