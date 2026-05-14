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
from pydantic import BaseModel, Field, field_validator


# ── Portfolio Models ──────────────────────────────────────────────

class PortfolioIn(BaseModel):
    """Request model for creating a new portfolio/account."""
    name: str = Field(..., min_length=1, max_length=100, description="账户名称")
    type: str = Field(default="portfolio", pattern="^(portfolio|account|strategy|group|main)$")
    parent_id: Optional[int] = Field(default=None, ge=1, description="父账户ID")
    currency: str = Field(default="CNY", pattern="^(CNY|USD|HKD|EUR)$")
    asset_class: str = Field(default="mixed", pattern="^(stock|bond|fund|futures|options|mixed)$")
    strategy: Optional[str] = Field(default=None, pattern="^(value|growth|balanced|index|quant)$")
    benchmark: Optional[str] = Field(default=None, max_length=20)
    status: str = Field(default="active", pattern="^(active|frozen|closed)$")
    initial_capital: float = Field(default=0.0, ge=0, description="初始本金")
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('账户名称不能为空')
        return v.strip()


class PortfolioUpdate(BaseModel):
    """Request model for updating portfolio properties."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    type: Optional[str] = Field(default=None, pattern="^(portfolio|account|strategy|group|main)$")
    parent_id: Optional[int] = Field(default=None, ge=1)
    currency: Optional[str] = Field(default=None, pattern="^(CNY|USD|HKD|EUR)$")
    asset_class: Optional[str] = Field(default=None, pattern="^(stock|bond|fund|futures|options|mixed)$")
    strategy: Optional[str] = Field(default=None, pattern="^(value|growth|balanced|index|quant)$")
    benchmark: Optional[str] = Field(default=None, max_length=20)
    status: Optional[str] = Field(default=None, pattern="^(active|frozen|closed)$")
    initial_capital: Optional[float] = Field(default=None, ge=0)
    description: Optional[str] = Field(default=None, max_length=500)


# ── Position Models ──────────────────────────────────────────────

class PositionIn(BaseModel):
    """Request model for creating/updating a position."""
    portfolio_id: int = Field(..., ge=1, description="账户ID")
    symbol: str = Field(..., min_length=1, max_length=20, description="股票代码")
    shares: int = Field(..., ge=0, description="持仓数量")
    avg_cost: float = Field(..., ge=0, description="平均成本")


class PositionUpdate(BaseModel):
    """Request model for updating position shares and/or average cost."""
    shares: Optional[int] = Field(default=None, ge=0)
    avg_cost: Optional[float] = Field(default=None, ge=0)


# ── Transaction Models ──────────────────────────────────────────────

class TransactionIn(BaseModel):
    """Request model for recording a financial transaction."""
    portfolio_id: int = Field(..., ge=1, description="账户ID")
    type: str = Field(..., pattern="^(deposit|withdraw|transfer_in|transfer_out|dividend|fee)$")
    amount: float = Field(..., description="金额")
    balance_after: float = Field(..., ge=0, description="交易后余额")
    counterparty_id: Optional[int] = Field(default=None, ge=1)
    related_symbol: Optional[str] = Field(default=None, max_length=20)
    note: Optional[str] = Field(default=None, max_length=500)
    operator: str = Field(default="user", max_length=50)


class TransferIn(BaseModel):
    """Request model for transferring funds between accounts."""
    from_portfolio_id: int = Field(..., ge=1, description="转出账户ID")
    to_portfolio_id: int = Field(..., ge=1, description="转入账户ID")
    amount: float = Field(..., gt=0, description="划转金额")
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator('to_portfolio_id')
    @classmethod
    def validate_different_accounts(cls, v: int, info) -> int:
        if 'from_portfolio_id' in info.data and info.data['from_portfolio_id'] == v:
            raise ValueError('转出账户和转入账户不能相同')
        return v


class CashOpIn(BaseModel):
    """Request model for cash deposit/withdrawal operations."""
    amount: float = Field(..., description="金额")
    operator: str = Field(default="user", max_length=50)
    note: Optional[str] = Field(default=None, max_length=500)


# ── Lot Trading Models ──────────────────────────────────────────────

class BuyIn(BaseModel):
    """Request model for buying a lot (opening position)."""
    symbol: str = Field(..., min_length=1, max_length=20, description="股票代码")
    shares: int = Field(..., gt=0, description="买入数量")
    buy_price: float = Field(..., gt=0, description="买入价格")
    buy_date: Optional[str] = Field(default=None, max_length=10)
    order_id: Optional[str] = Field(default=None, max_length=50)

    @field_validator('buy_date')
    @classmethod
    def validate_buy_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from datetime import datetime
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f'Invalid date format: {v}, expected YYYY-MM-DD')


class SellIn(BaseModel):
    """Request model for selling a lot (closing position via FIFO)."""
    symbol: str = Field(..., min_length=1, max_length=20, description="股票代码")
    shares: int = Field(..., gt=0, description="卖出数量")
    sell_price: float = Field(..., gt=0, description="卖出价格")
    order_id: Optional[str] = Field(default=None, max_length=50)
