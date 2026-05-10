"""
Portfolio Schemas - Pydantic Models for Portfolio Router

This module contains all Pydantic request/response models used by the portfolio router.
Extracted from portfolio.py for better code organization and maintainability.

Models:
- PortfolioIn: Create new portfolio/account
- PortfolioUpdate: Update portfolio properties
- PositionIn: Create/update position
- PositionUpdate: Update position shares/cost
- TransactionIn: Record financial transaction
- TransferIn: Transfer between accounts
- CashOpIn: Cash deposit/withdrawal
- BuyIn: Buy lot (open position)
- SellIn: Sell lot (close position)
"""

from typing import Optional
from pydantic import BaseModel


# ── Portfolio Models ──────────────────────────────────────────────

class PortfolioIn(BaseModel):
    """Request model for creating a new portfolio/account."""
    name: str
    type: str = "portfolio"   # portfolio | account | strategy | group
    parent_id: Optional[int] = None
    currency: str = "CNY"  # CNY | USD | HKD
    asset_class: str = "mixed"  # stock | bond | fund | futures | options | mixed
    strategy: Optional[str] = None  # value | growth | balanced | index | quant
    benchmark: Optional[str] = None  # 000001 | 000300 | 399001 | 399006
    status: str = "active"  # active | frozen | closed
    initial_capital: float = 0.0
    description: Optional[str] = None


class PortfolioUpdate(BaseModel):
    """Request model for updating portfolio properties."""
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[int] = None
    currency: Optional[str] = None
    asset_class: Optional[str] = None
    strategy: Optional[str] = None
    benchmark: Optional[str] = None
    status: Optional[str] = None
    initial_capital: Optional[float] = None
    description: Optional[str] = None


# ── Position Models ──────────────────────────────────────────────

class PositionIn(BaseModel):
    """Request model for creating/updating a position."""
    portfolio_id: int
    symbol: str
    shares: int
    avg_cost: float


class PositionUpdate(BaseModel):
    """Request model for updating position shares and/or average cost."""
    shares: Optional[int] = None
    avg_cost: Optional[float] = None


# ── Transaction Models ──────────────────────────────────────────────

class TransactionIn(BaseModel):
    """Request model for recording a financial transaction."""
    portfolio_id: int
    type: str          # deposit | withdraw | transfer_in | transfer_out | dividend | fee
    amount: float
    balance_after: float
    counterparty_id: Optional[int] = None
    related_symbol: Optional[str] = None
    note: Optional[str] = None
    operator: str = "user"


class TransferIn(BaseModel):
    """Request model for transferring funds between accounts."""
    from_portfolio_id: int
    to_portfolio_id: int
    amount: float
    note: Optional[str] = None


class CashOpIn(BaseModel):
    """Request model for cash deposit/withdrawal operations."""
    amount: float
    operator: str = "user"
    note: Optional[str] = None


# ── Lot Trading Models ──────────────────────────────────────────────

class BuyIn(BaseModel):
    """Request model for buying a lot (opening position)."""
    symbol:    str
    shares:    int
    buy_price: float
    buy_date:  Optional[str] = None
    order_id:  Optional[str] = None


class SellIn(BaseModel):
    """Request model for selling a lot (closing position via FIFO)."""
    symbol:    str
    shares:    int
    sell_price: float
    order_id:  Optional[str] = None
