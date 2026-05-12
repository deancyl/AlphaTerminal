"""
归因分析模块

包含:
- Brinson归因模型
- Campisi固收归因（待实现）
"""
from .brinson import (
    calculate_brinson_attribution,
    aggregate_to_sectors,
    get_sector_from_symbol,
    BrinsonResult,
    SectorContribution
)

__all__ = [
    'calculate_brinson_attribution',
    'aggregate_to_sectors',
    'get_sector_from_symbol',
    'BrinsonResult',
    'SectorContribution'
]
