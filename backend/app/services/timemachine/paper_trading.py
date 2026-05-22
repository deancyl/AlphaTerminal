"""
Paper Trading State Machine for Time-Machine Replay.

Manages portfolio state, positions, and trade execution during historical replay.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class TradeAction(Enum):
    BUY = "buy"
    SELL = "sell"


class PaperTradingError(Exception):
    """Paper trading error."""

    pass


@dataclass
class Position:
    """Single position in the portfolio."""

    symbol: str
    quantity: float
    avg_cost: float
    opened_at: str
    opened_bar_index: int

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        return (current_price - self.avg_cost) * self.quantity

    def unrealized_pnl_pct(self, current_price: float) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (current_price - self.avg_cost) / self.avg_cost * 100


@dataclass
class Trade:
    """Single trade record."""

    id: str
    date: str
    bar_index: int
    action: TradeAction
    price: float
    quantity: float
    value: float
    commission: float = 0.0
    pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PaperPortfolio:
    """
    Paper trading portfolio for time-machine replay.

    Tracks:
    - Cash balance
    - Positions (with average cost)
    - Trade history
    - P&L calculations
    """

    initial_capital: float
    cash: float = field(default_factory=lambda: 0.0)
    positions: List[Position] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)

    COMMISSION_RATE = 0.0003
    MIN_COMMISSION = 5.0

    def __post_init__(self):
        self.cash = self.initial_capital

    def total_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value at current prices."""
        positions_value = sum(
            pos.market_value(current_prices.get(pos.symbol, pos.avg_cost))
            for pos in self.positions
        )
        return self.cash + positions_value

    def total_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total P&L from initial capital."""
        return self.total_value(current_prices) - self.initial_capital

    def total_pnl_pct(self, current_prices: Dict[str, float]) -> float:
        """Calculate total P&L percentage."""
        if self.initial_capital == 0:
            return 0.0
        return self.total_pnl(current_prices) / self.initial_capital * 100

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        for pos in self.positions:
            if pos.symbol == symbol:
                return pos
        return None

    def execute_trade(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
        current_date: str,
        current_bar_index: int,
    ) -> Trade:
        """
        Execute a paper trade.

        Args:
            action: "buy" or "sell"
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            current_date: Current replay date
            current_bar_index: Current bar index

        Returns:
            Trade record

        Raises:
            PaperTradingError: If trade cannot be executed
        """
        try:
            trade_action = TradeAction(action.lower())
        except ValueError:
            raise PaperTradingError(
                f"Invalid action: {action}. Must be 'buy' or 'sell'"
            )

        if quantity <= 0:
            raise PaperTradingError("Quantity must be positive")

        if price <= 0:
            raise PaperTradingError("Price must be positive")

        trade_value = quantity * price
        commission = max(trade_value * self.COMMISSION_RATE, self.MIN_COMMISSION)

        if trade_action == TradeAction.BUY:
            total_cost = trade_value + commission

            if self.cash < total_cost:
                raise PaperTradingError(
                    f"Insufficient cash. Need {total_cost:.2f}, have {self.cash:.2f}"
                )

            self.cash -= total_cost

            existing = self.get_position(symbol)
            if existing:
                total_qty = existing.quantity + quantity
                new_avg_cost = (
                    existing.avg_cost * existing.quantity + trade_value
                ) / total_qty
                existing.quantity = total_qty
                existing.avg_cost = new_avg_cost
            else:
                self.positions.append(
                    Position(
                        symbol=symbol,
                        quantity=quantity,
                        avg_cost=price,
                        opened_at=current_date,
                        opened_bar_index=current_bar_index,
                    )
                )

            trade = Trade(
                id=str(uuid.uuid4())[:8],
                date=current_date,
                bar_index=current_bar_index,
                action=trade_action,
                price=price,
                quantity=quantity,
                value=trade_value,
                commission=commission,
                pnl=0.0,
            )

        else:  # SELL
            existing = self.get_position(symbol)
            if not existing:
                raise PaperTradingError(f"No position for {symbol}")

            if existing.quantity < quantity:
                raise PaperTradingError(
                    f"Insufficient shares. Have {existing.quantity}, trying to sell {quantity}"
                )

            realized_pnl = (price - existing.avg_cost) * quantity - commission

            self.cash += trade_value - commission

            existing.quantity -= quantity
            if existing.quantity <= 0:
                self.positions = [p for p in self.positions if p.symbol != symbol]

            trade = Trade(
                id=str(uuid.uuid4())[:8],
                date=current_date,
                bar_index=current_bar_index,
                action=trade_action,
                price=price,
                quantity=quantity,
                value=trade_value,
                commission=commission,
                pnl=realized_pnl,
            )

        self.trades.append(trade)
        return trade

    def to_dict(
        self, current_prices: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Serialize portfolio to dict."""
        current_prices = current_prices or {}

        positions_dict = []
        for pos in self.positions:
            price = current_prices.get(pos.symbol, pos.avg_cost)
            positions_dict.append(
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "market_value": pos.market_value(price),
                    "unrealized_pnl": pos.unrealized_pnl(price),
                    "unrealized_pnl_pct": pos.unrealized_pnl_pct(price),
                }
            )

        return {
            "initial_capital": self.initial_capital,
            "cash": round(self.cash, 2),
            "positions": positions_dict,
            "total_value": round(self.total_value(current_prices), 2),
            "total_pnl": round(self.total_pnl(current_prices), 2),
            "total_pnl_pct": round(self.total_pnl_pct(current_prices), 2),
            "trade_count": len(self.trades),
        }

    def trades_to_dict(self) -> List[Dict[str, Any]]:
        """Serialize trades to list of dicts."""
        return [
            {
                "id": t.id,
                "date": t.date,
                "action": t.action.value,
                "price": round(t.price, 2),
                "quantity": t.quantity,
                "value": round(t.value, 2),
                "commission": round(t.commission, 2),
                "pnl": round(t.pnl, 2),
            }
            for t in self.trades
        ]
