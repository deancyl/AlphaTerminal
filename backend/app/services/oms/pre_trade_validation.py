"""
Pre-Trade Validation Middleware

Validates orders before submission to broker:
- Cash availability check
- Position limit check
- Margin check (if applicable)
- Price sanity check (within 10% of market)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
import sqlite3

from app.db.database import _get_conn


@dataclass
class ValidationError:
    """Single validation error."""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Result of pre-trade validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_error(
        self,
        code: str,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.errors.append(ValidationError(code=code, message=message, field=field, details=details))
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class PreTradeValidator:
    """
    Pre-trade validation middleware.
    
    Validates orders before submission:
    1. Cash availability (for buy orders)
    2. Position availability (for sell orders)
    3. Price sanity (within 10% of market)
    4. Position limits (max position size)
    """
    
    MAX_POSITION_PCT = 0.3  # Max 30% of portfolio in single position
    PRICE_SANITY_PCT = 0.1  # Max 10% deviation from market price
    
    def __init__(self, broker_adapter: Optional[Any] = None):
        self.broker_adapter = broker_adapter
    
    def validate(
        self,
        portfolio_id: int,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float],
        order_type: str,
    ) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        
        if side == "buy":
            self._validate_buy_order(portfolio_id, symbol, quantity, price, order_type, result)
        elif side == "sell":
            self._validate_sell_order(portfolio_id, symbol, quantity, result)
        
        if price is not None and order_type == "limit":
            self._validate_price_sanity(symbol, price, result)
        
        return result
    
    def _validate_buy_order(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: int,
        price: Optional[float],
        order_type: str,
        result: ValidationResult,
    ) -> None:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT cash_balance FROM portfolios WHERE id=?",
                (portfolio_id,),
            ).fetchone()
            
            if not row:
                result.add_error("PORTFOLIO_NOT_FOUND", f"Portfolio {portfolio_id} not found")
                return
            
            cash_balance = row["cash_balance"] or 0.0
            
            if self.broker_adapter:
                market_price = self.broker_adapter.get_market_price(symbol)
            else:
                market_price = self._get_cached_price(symbol)
            
            estimated_cost = quantity * (price or market_price)
            
            if estimated_cost > cash_balance:
                result.add_error(
                    "INSUFFICIENT_CASH",
                    f"Insufficient cash: need {estimated_cost:.2f}, have {cash_balance:.2f}",
                    field="cash_balance",
                    details={
                        "required": estimated_cost,
                        "available": cash_balance,
                        "shortfall": estimated_cost - cash_balance,
                    }
                )
            
            self._check_position_limit(portfolio_id, symbol, quantity, market_price, result)
            
        finally:
            conn.close()
    
    def _validate_sell_order(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: int,
        result: ValidationResult,
    ) -> None:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT total_shares FROM position_summary WHERE portfolio_id=? AND symbol=?",
                (portfolio_id, symbol),
            ).fetchone()
            
            if not row or row["total_shares"] < quantity:
                available = row["total_shares"] if row else 0
                result.add_error(
                    "INSUFFICIENT_POSITION",
                    f"Insufficient position: need {quantity}, have {available}",
                    field="shares",
                    details={
                        "required": quantity,
                        "available": available,
                        "shortfall": quantity - available,
                    }
                )
        finally:
            conn.close()
    
    def _validate_price_sanity(
        self,
        symbol: str,
        price: float,
        result: ValidationResult,
    ) -> None:
        if self.broker_adapter:
            market_price = self.broker_adapter.get_market_price(symbol)
        else:
            market_price = self._get_cached_price(symbol)
        
        if market_price <= 0:
            return
        
        deviation = abs(price - market_price) / market_price
        
        if deviation > self.PRICE_SANITY_PCT:
            result.add_warning(
                f"Price {price:.2f} deviates {deviation*100:.1f}% from market {market_price:.2f}"
            )
    
    def _check_position_limit(
        self,
        portfolio_id: int,
        symbol: str,
        quantity: int,
        price: float,
        result: ValidationResult,
    ) -> None:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT cash_balance, initial_capital FROM portfolios WHERE id=?",
                (portfolio_id,),
            ).fetchone()
            
            if not row:
                return
            
            total_capital = row["cash_balance"] + row["initial_capital"]
            
            if total_capital <= 0:
                return
            
            new_position_value = quantity * price
            
            pct_of_portfolio = new_position_value / total_capital
            
            if pct_of_portfolio > self.MAX_POSITION_PCT:
                result.add_warning(
                    f"Position would be {pct_of_portfolio*100:.1f}% of portfolio (max {self.MAX_POSITION_PCT*100:.0f}%)"
                )
        finally:
            conn.close()
    
    def _get_cached_price(self, symbol: str) -> float:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT price FROM market_data_realtime WHERE symbol=?",
                (symbol,),
            ).fetchone()
            return row["price"] if row else 100.0
        finally:
            conn.close()


def validate_order(
    portfolio_id: int,
    symbol: str,
    side: str,
    quantity: int,
    price: Optional[float],
    order_type: str,
    broker_adapter: Optional[Any] = None,
) -> ValidationResult:
    validator = PreTradeValidator(broker_adapter)
    return validator.validate(portfolio_id, symbol, side, quantity, price, order_type)