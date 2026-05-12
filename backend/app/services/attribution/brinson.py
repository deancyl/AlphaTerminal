"""
Brinson归因分析模型

将组合超额收益分解为:
1. 配置效应 (Allocation Effect)
2. 选择效应 (Selection Effect)  
3. 交互效应 (Interaction Effect)

公式:
- 配置效应 = Σ (w_p - w_b) * R_b
- 选择效应 = Σ w_b * (R_p - R_b)
- 交互效应 = Σ (w_p - w_b) * (R_p - R_b)
- 总超额收益 = 配置效应 + 选择效应 + 交互效应

其中:
- w_p: 组合权重
- w_b: 基准权重
- R_p: 组合收益率
- R_b: 基准收益率
"""
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SectorContribution(BaseModel):
    sector: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_effect: float

class BrinsonResult(BaseModel):
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    total_excess_return: float
    sector_contributions: List[SectorContribution]
    period_start: str
    period_end: str

def calculate_brinson_attribution(
    portfolio_weights: Dict[str, float],
    portfolio_returns: Dict[str, float],
    benchmark_weights: Dict[str, float],
    benchmark_returns: Dict[str, float],
    period_start: str,
    period_end: str
) -> BrinsonResult:
    """
    计算Brinson归因分析
    
    Args:
        portfolio_weights: 组合各板块权重 {sector: weight}
        portfolio_returns: 组合各板块收益率 {sector: return}
        benchmark_weights: 基准各板块权重 {sector: weight}
        benchmark_returns: 基准各板块收益率 {sector: return}
        period_start: 开始日期
        period_end: 结束日期
    
    Returns:
        BrinsonResult: 归因分析结果
    """
    sectors = set(portfolio_weights.keys()) | set(benchmark_weights.keys())
    
    sector_contributions = []
    total_allocation = 0.0
    total_selection = 0.0
    total_interaction = 0.0
    
    for sector in sectors:
        w_p = portfolio_weights.get(sector, 0.0)
        w_b = benchmark_weights.get(sector, 0.0)
        r_p = portfolio_returns.get(sector, 0.0)
        r_b = benchmark_returns.get(sector, 0.0)
        
        # 配置效应: (w_p - w_b) * R_b
        allocation = (w_p - w_b) * r_b
        
        # 选择效应: w_b * (R_p - R_b)
        selection = w_b * (r_p - r_b)
        
        # 交互效应: (w_p - w_b) * (R_p - R_b)
        interaction = (w_p - w_b) * (r_p - r_b)
        
        # 总效应
        total_effect = allocation + selection + interaction
        
        sector_contributions.append(SectorContribution(
            sector=sector,
            portfolio_weight=w_p,
            benchmark_weight=w_b,
            portfolio_return=r_p,
            benchmark_return=r_b,
            allocation_effect=allocation,
            selection_effect=selection,
            interaction_effect=interaction,
            total_effect=total_effect
        ))
        
        total_allocation += allocation
        total_selection += selection
        total_interaction += interaction
    
    return BrinsonResult(
        allocation_effect=total_allocation,
        selection_effect=total_selection,
        interaction_effect=total_interaction,
        total_excess_return=total_allocation + total_selection + total_interaction,
        sector_contributions=sector_contributions,
        period_start=period_start,
        period_end=period_end
    )

def get_sector_from_symbol(symbol: str) -> str:
    """
    根据股票代码获取行业分类
    
    简化版本，实际应该从数据源获取
    """
    # 简化映射
    sector_map = {
        '600519': '白酒',
        '000858': '白酒',
        '000333': '家电',
        '600036': '银行',
        '601318': '保险',
        '000001': '银行',
        '300750': '新能源',
        '002594': '汽车',
    }
    return sector_map.get(symbol, '其他')

def aggregate_to_sectors(
    positions: List[Dict],
    returns: Dict[str, float]
) -> tuple[Dict[str, float], Dict[str, float]]:
    """
    将持仓聚合到行业层面
    
    Args:
        positions: 持仓列表 [{symbol, weight, ...}]
        returns: 各股票收益率 {symbol: return}
    
    Returns:
        (sector_weights, sector_returns): 行业权重和收益率
    """
    sector_weights = {}
    sector_returns = {}
    sector_weighted_returns = {}
    
    for pos in positions:
        symbol = pos.get('symbol', '')
        weight = pos.get('weight', 0.0)
        ret = returns.get(symbol, 0.0)
        
        sector = get_sector_from_symbol(symbol)
        
        # 累加行业权重
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
        
        # 累加行业加权收益（用于计算行业收益率）
        sector_weighted_returns[sector] = sector_weighted_returns.get(sector, 0.0) + weight * ret
    
    # 计算行业收益率（加权平均）
    for sector in sector_weights:
        if sector_weights[sector] > 0:
            sector_returns[sector] = sector_weighted_returns[sector] / sector_weights[sector]
        else:
            sector_returns[sector] = 0.0
    
    return sector_weights, sector_returns
