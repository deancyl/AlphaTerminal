"""
Portfolio Router - Aggregated from domain modules.

This module provides a unified router for all portfolio-related endpoints,
split across multiple domain modules for maintainability.

Modules:
- accounts.py: Portfolio CRUD operations (3 endpoints)
- positions.py: Position management, PnL, snapshots (7 endpoints)
- analytics.py: Attribution, performance, risk, benchmark (4 endpoints)
- cash.py: Cash operations, transfers, transactions (6 endpoints)
- lots.py: Lot trading, conservation, tree, echarts (9 endpoints)

Total: 29 endpoints
"""
from fastapi import APIRouter

from .accounts import router as accounts_router
from .positions import router as positions_router
from .analytics import router as analytics_router
from .cash import router as cash_router
from .lots import router as lots_router

from .schemas import (
    PortfolioIn,
    PortfolioUpdate,
    PositionIn,
    PositionUpdate,
    TransactionIn,
    TransferIn,
    CashOpIn,
    BuyIn,
    SellIn,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

router.include_router(accounts_router)
router.include_router(positions_router)
router.include_router(analytics_router)
router.include_router(cash_router)
router.include_router(lots_router)

__all__ = [
    "router",
    "PortfolioIn",
    "PortfolioUpdate",
    "PositionIn",
    "PositionUpdate",
    "TransactionIn",
    "TransferIn",
    "CashOpIn",
    "BuyIn",
    "SellIn",
]
