"""
Attribution Analysis Module

Contains:
- FactorRegistry: Factor definitions and calculations
- AttributionEngine: Multi-factor attribution analysis
- Brinson: Brinson attribution model
"""

from .factor_registry import (
    FactorCategory,
    FactorDefinition,
    FactorRegistry,
    get_factor_registry,
)
from .attribution_engine import (
    FactorContribution,
    AttributionResult,
    AttributionEngine,
    get_attribution_engine,
)
from .brinson import (
    calculate_brinson_attribution,
    aggregate_to_sectors,
    get_sector_from_symbol,
    BrinsonResult,
    SectorContribution,
)

__all__ = [
    "FactorCategory",
    "FactorDefinition",
    "FactorRegistry",
    "get_factor_registry",
    "FactorContribution",
    "AttributionResult",
    "AttributionEngine",
    "get_attribution_engine",
    "calculate_brinson_attribution",
    "aggregate_to_sectors",
    "get_sector_from_symbol",
    "BrinsonResult",
    "SectorContribution",
]
