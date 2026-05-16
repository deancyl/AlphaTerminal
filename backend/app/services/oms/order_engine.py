"""
Order Execution Engine

Core OMS component that manages order lifecycle:
- Order creation and validation
- State transitions with validation
- Broker submission
- Fill tracking
- Audit trail integration
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.db.database import _get_conn, _lock

from .order_status import (
    OrderStatus,
    is_valid_transition,
    get_allowed_transitions,
    is_terminal_status,
)
from .broker_adapter import BrokerAdapter, MockBrokerAdapter, ExecutionReport
from .pre_trade_validation import PreTradeValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Order data structure with all fields."""
    id: Optional[int] = None
    portfolio_id: int = 0
    symbol: str = ""
    side: str = ""  # buy/sell
    order_type: str = ""  # market/limit/stop
    quantity: int = 0
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.STAGED
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    reject_reason: Optional[str] = None
    broker_order_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "created_at": self.created_at,
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "cancelled_at": self.cancelled_at,
            "reject_reason": self.reject_reason,
            "broker_order_id": self.broker_order_id,
        }


class OrderExecutionEngine:
    """
    Order Execution Engine - Core OMS Component.
    
    Manages complete order lifecycle:
    1. create_order() - Create order in STAGED state
    2. validate_order() - Pre-trade validation
    3. submit_order() - Submit to broker
    4. cancel_order() - Cancel pending order
    5. process_fill() - Process execution report
    
    All state transitions are validated against VALID_TRANSITIONS.
    """
    
    def __init__(
        self,
        broker_adapter: Optional[BrokerAdapter] = None,
        enable_audit: bool = True,
    ):
        self.broker = broker_adapter or MockBrokerAdapter()
        self.validator = PreTradeValidator(self.broker)
        self.enable_audit = enable_audit
    
    def create_order(
        self,
        portfolio_id: int,
        symbol: str,
        side: str,
        quantity: int,
        price: Optional[float],
        order_type: str = "limit",
    ) -> Order:
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}")
        if order_type not in ("market", "limit", "stop"):
            raise ValueError(f"Invalid order_type: {order_type}")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive: {quantity}")
        if order_type == "limit" and price is None:
            raise ValueError("Limit order requires price")
        
        order = Order(
            portfolio_id=portfolio_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status=OrderStatus.STAGED,
        )
        
        order.id = self._save_order(order)
        
        self._log_audit(
            action="order_created",
            order=order,
            details={"initial_status": "staged"},
        )
        
        logger.info(f"[OMS] Created order {order.id}: {symbol} {side} {quantity}@{price}")
        return order
    
    def validate_order(self, order: Order) -> ValidationResult:
        if order.status != OrderStatus.STAGED:
            from .pre_trade_validation import ValidationError
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(code="INVALID_STATUS", message=f"Cannot validate order in {order.status.value} state")],
            )
        
        result = self.validator.validate(
            portfolio_id=order.portfolio_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            order_type=order.order_type,
        )
        
        self._log_audit(
            action="order_validated",
            order=order,
            details={"is_valid": result.is_valid, "errors": [e.message for e in result.errors]},
        )
        
        return result
    
    def submit_order(self, order: Order) -> Order:
        if not is_valid_transition(order.status, OrderStatus.SUBMITTED):
            raise InvalidStateTransitionError(
                f"Cannot submit order in {order.status.value} state. "
                f"Allowed: {[s.value for s in get_allowed_transitions(order.status)]}"
            )
        
        validation = self.validate_order(order)
        if not validation.is_valid:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "; ".join(e.message for e in validation.errors)
            self._update_order(order)
            
            self._log_audit(
                action="order_rejected",
                order=order,
                details={"reason": order.reject_reason},
            )
            
            logger.warning(f"[OMS] Order {order.id} rejected: {order.reject_reason}")
            return order
        
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now().isoformat()
        self._update_order(order)
        
        report = self.broker.submit_order(
            order_id=str(order.id),
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
        )
        
        if report.status == OrderStatus.REJECTED:
            order.status = OrderStatus.REJECTED
            order.reject_reason = report.reject_reason
        elif report.status == OrderStatus.FILLED:
            order.status = OrderStatus.FILLED
            order.filled_quantity = report.filled_quantity
            order.avg_fill_price = report.avg_fill_price
            order.filled_at = datetime.now().isoformat()
            order.broker_order_id = report.broker_order_id
            self._execute_trade(order)
        elif report.status == OrderStatus.PARTIAL_FILLED:
            order.status = OrderStatus.PARTIAL_FILLED
            order.filled_quantity = report.filled_quantity
            order.avg_fill_price = report.avg_fill_price
            order.broker_order_id = report.broker_order_id
        else:
            order.status = OrderStatus.PENDING
            order.broker_order_id = report.broker_order_id
        
        self._update_order(order)
        
        self._log_audit(
            action="order_submitted",
            order=order,
            details={"broker_order_id": order.broker_order_id, "status": order.status.value},
        )
        
        logger.info(f"[OMS] Order {order.id} submitted, status={order.status.value}")
        return order
    
    def cancel_order(self, order_id: int) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {order_id} not found")
        
        if not is_valid_transition(order.status, OrderStatus.CANCELLED):
            raise InvalidStateTransitionError(
                f"Cannot cancel order in {order.status.value} state. "
                f"Allowed: {[s.value for s in get_allowed_transitions(order.status)]}"
            )
        
        if order.broker_order_id:
            self.broker.cancel_order(str(order_id), order.broker_order_id)
        
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now().isoformat()
        self._update_order(order)
        
        self._log_audit(
            action="order_cancelled",
            order=order,
            details={"cancelled_at": order.cancelled_at},
        )
        
        logger.info(f"[OMS] Order {order_id} cancelled")
        return order
    
    def process_fill(
        self,
        order_id: int,
        filled_quantity: int,
        fill_price: float,
    ) -> Order:
        order = self.get_order(order_id)
        if order is None:
            raise OrderNotFoundError(f"Order {order_id} not found")
        
        if order.status not in (OrderStatus.PENDING, OrderStatus.PARTIAL_FILLED):
            raise InvalidStateTransitionError(
                f"Cannot fill order in {order.status.value} state"
            )
        
        new_filled = order.filled_quantity + filled_quantity
        
        if new_filled > order.quantity:
            raise ValueError(f"Fill quantity exceeds order: {new_filled} > {order.quantity}")
        
        total_value = order.avg_fill_price * order.filled_quantity + fill_price * filled_quantity
        order.avg_fill_price = total_value / new_filled if new_filled > 0 else 0.0
        order.filled_quantity = new_filled
        
        if new_filled == order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now().isoformat()
            self._execute_trade(order)
        else:
            order.status = OrderStatus.PARTIAL_FILLED
        
        self._update_order(order)
        
        self._log_audit(
            action="order_filled",
            order=order,
            details={"filled_quantity": filled_quantity, "fill_price": fill_price},
        )
        
        logger.info(f"[OMS] Order {order_id} fill: +{filled_quantity}@{fill_price}")
        return order
    
    def get_order(self, order_id: int) -> Optional[Order]:
        conn = _get_conn()
        try:
            row = conn.execute(
                """SELECT id, portfolio_id, symbol, side, order_type, quantity, price,
                          status, filled_quantity, avg_fill_price, created_at,
                          submitted_at, filled_at, cancelled_at, reject_reason, broker_order_id
                   FROM orders WHERE id=?""",
                (order_id,),
            ).fetchone()
            
            if row is None:
                return None
            
            return Order(
                id=row["id"],
                portfolio_id=row["portfolio_id"],
                symbol=row["symbol"],
                side=row["side"],
                order_type=row["order_type"],
                quantity=row["quantity"],
                price=row["price"],
                status=OrderStatus(row["status"]),
                filled_quantity=row["filled_quantity"],
                avg_fill_price=row["avg_fill_price"],
                created_at=row["created_at"],
                submitted_at=row["submitted_at"],
                filled_at=row["filled_at"],
                cancelled_at=row["cancelled_at"],
                reject_reason=row["reject_reason"],
                broker_order_id=row["broker_order_id"],
            )
        finally:
            conn.close()
    
    def get_order_status(self, order_id: int) -> Optional[OrderStatus]:
        order = self.get_order(order_id)
        return order.status if order else None
    
    def get_open_orders(self, portfolio_id: int) -> List[Order]:
        conn = _get_conn()
        try:
            rows = conn.execute(
                """SELECT id, portfolio_id, symbol, side, order_type, quantity, price,
                          status, filled_quantity, avg_fill_price, created_at,
                          submitted_at, filled_at, cancelled_at, reject_reason, broker_order_id
                   FROM orders
                   WHERE portfolio_id=? AND status IN ('staged', 'submitted', 'pending', 'partial')
                   ORDER BY created_at DESC""",
                (portfolio_id,),
            ).fetchall()
            
            return [self._row_to_order(row) for row in rows]
        finally:
            conn.close()
    
    def get_orders_by_portfolio(
        self,
        portfolio_id: int,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        conn = _get_conn()
        try:
            if status:
                rows = conn.execute(
                    """SELECT id, portfolio_id, symbol, side, order_type, quantity, price,
                              status, filled_quantity, avg_fill_price, created_at,
                              submitted_at, filled_at, cancelled_at, reject_reason, broker_order_id
                       FROM orders
                       WHERE portfolio_id=? AND status=?
                       ORDER BY created_at DESC
                       LIMIT ? OFFSET ?""",
                    (portfolio_id, status.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, portfolio_id, symbol, side, order_type, quantity, price,
                              status, filled_quantity, avg_fill_price, created_at,
                              submitted_at, filled_at, cancelled_at, reject_reason, broker_order_id
                       FROM orders
                       WHERE portfolio_id=?
                       ORDER BY created_at DESC
                       LIMIT ? OFFSET ?""",
                    (portfolio_id, limit, offset),
                ).fetchall()
            
            return [self._row_to_order(row) for row in rows]
        finally:
            conn.close()
    
    def _row_to_order(self, row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            portfolio_id=row["portfolio_id"],
            symbol=row["symbol"],
            side=row["side"],
            order_type=row["order_type"],
            quantity=row["quantity"],
            price=row["price"],
            status=OrderStatus(row["status"]),
            filled_quantity=row["filled_quantity"],
            avg_fill_price=row["avg_fill_price"],
            created_at=row["created_at"],
            submitted_at=row["submitted_at"],
            filled_at=row["filled_at"],
            cancelled_at=row["cancelled_at"],
            reject_reason=row["reject_reason"],
            broker_order_id=row["broker_order_id"],
        )
    
    def _save_order(self, order: Order) -> int:
        conn = _get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO orders (
                    portfolio_id, symbol, side, order_type, quantity, price,
                    status, filled_quantity, avg_fill_price, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order.portfolio_id,
                    order.symbol,
                    order.side,
                    order.order_type,
                    order.quantity,
                    order.price,
                    order.status.value,
                    order.filled_quantity,
                    order.avg_fill_price,
                    order.created_at,
                ),
            )
            order_id = cursor.lastrowid or 0
            conn.commit()
            return order_id
        finally:
            conn.close()
    
    def _update_order(self, order: Order) -> None:
        conn = _get_conn()
        try:
            conn.execute(
                """UPDATE orders SET
                    status=?, filled_quantity=?, avg_fill_price=?,
                    submitted_at=?, filled_at=?, cancelled_at=?,
                    reject_reason=?, broker_order_id=?
                WHERE id=?""",
                (
                    order.status.value,
                    order.filled_quantity,
                    order.avg_fill_price,
                    order.submitted_at,
                    order.filled_at,
                    order.cancelled_at,
                    order.reject_reason,
                    order.broker_order_id,
                    order.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    
    def _execute_trade(self, order: Order) -> None:
        if order.status != OrderStatus.FILLED:
            return
        
        from app.services.trading import execute_buy, execute_sell
        
        try:
            if order.side == "buy":
                execute_buy(
                    portfolio_id=order.portfolio_id,
                    symbol=order.symbol,
                    shares=order.filled_quantity,
                    buy_price=order.avg_fill_price,
                    order_id=str(order.id),
                )
            else:
                execute_sell(
                    portfolio_id=order.portfolio_id,
                    symbol=order.symbol,
                    shares=order.filled_quantity,
                    sell_price=order.avg_fill_price,
                    order_id=str(order.id),
                )
            
            logger.info(f"[OMS] Trade executed: {order.side} {order.filled_quantity} {order.symbol}@{order.avg_fill_price}")
        except Exception as e:
            logger.error(f"[OMS] Trade execution failed: {e}")
            raise
    
    def _log_audit(self, action: str, order: Order, details: Dict[str, Any]) -> None:
        if not self.enable_audit:
            return
        
        try:
            from app.services.audit_chain import log_audit_event
            
            log_audit_event(
                actor_id="oms",
                action=action,
                resource_type="order",
                resource_id=str(order.id),
                outcome="success",
                after_state=order.to_dict(),
            )
        except Exception as e:
            logger.warning(f"[OMS] Audit log failed: {e}")


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class OrderNotFoundError(Exception):
    """Raised when an order is not found."""
    pass