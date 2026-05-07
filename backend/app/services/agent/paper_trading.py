"""Paper Trading Service - 模拟交易引擎"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import uuid
import threading


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    status: OrderStatus
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None


class PaperTradingService:
    """模拟交易服务"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._orders: Dict[str, Order] = {}
        self._order_lock = threading.Lock()
        self._initialized = True

    def submit_order(self, symbol: str, side: str, quantity: float, price: float) -> Order:
        """提交订单"""
        with self._order_lock:
            order_id = str(uuid.uuid4())
            try:
                order_side = OrderSide(side.upper())
            except ValueError:
                raise ValueError(f"Invalid side: {side}. Must be BUY or SELL")

            if quantity <= 0:
                raise ValueError("Quantity must be positive")
            if price <= 0:
                raise ValueError("Price must be positive")

            order = Order(
                id=order_id,
                symbol=symbol.upper(),
                side=order_side,
                quantity=quantity,
                price=price,
                status=OrderStatus.PENDING,
            )
            self._orders[order_id] = order
            return order

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        with self._order_lock:
            order = self._orders.get(order_id)
            if not order:
                return False
            if order.status == OrderStatus.FILLED:
                return False
            if order.status == OrderStatus.CANCELLED:
                return False
            order.status = OrderStatus.CANCELLED
            return True

    def list_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """列出订单"""
        with self._order_lock:
            if symbol is None:
                return list(self._orders.values())
            return [o for o in self._orders.values() if o.symbol == symbol.upper()]

    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单详情"""
        with self._order_lock:
            return self._orders.get(order_id)

    def fill_order(self, order_id: str, filled_price: float) -> bool:
        """成交订单（内部使用）"""
        with self._order_lock:
            order = self._orders.get(order_id)
            if not order:
                return False
            if order.status != OrderStatus.PENDING:
                return False
            order.status = OrderStatus.FILLED
            order.filled_price = filled_price
            order.filled_at = datetime.now()
            return True


def get_paper_trading_service() -> PaperTradingService:
    return PaperTradingService()