"""
Broker Adapter Interface

Defines the Protocol interface for broker integration.
All broker adapters must implement this interface for OMS compatibility.

Currently provides:
- BrokerAdapter: Protocol interface
- MockBrokerAdapter: Mock implementation for testing
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, List, Optional, Dict, Any

from .order_status import OrderStatus


@dataclass
class ExecutionReport:
    """Execution report from broker after order submission."""
    order_id: str
    status: OrderStatus
    broker_order_id: Optional[str] = None
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message: Optional[str] = None
    reject_reason: Optional[str] = None


class BrokerAdapter(Protocol):
    """
    Broker adapter interface for order execution.
    
    All broker adapters must implement this Protocol for OMS compatibility.
    This enables future integration with real brokers (IBKR, XTP, etc.)
    """
    
    def submit_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Optional[float],
    ) -> ExecutionReport:
        """
        Submit order to broker.
        
        Args:
            order_id: Internal order ID
            symbol: Stock symbol
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', or 'stop'
            quantity: Order quantity
            price: Limit price (None for market orders)
            
        Returns:
            ExecutionReport with broker response
        """
        ...
    
    def cancel_order(self, order_id: str, broker_order_id: Optional[str]) -> bool:
        """
        Cancel order at broker.
        
        Args:
            order_id: Internal order ID
            broker_order_id: Broker's order ID
            
        Returns:
            True if cancellation successful
        """
        ...
    
    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """
        Query order status from broker.
        
        Args:
            broker_order_id: Broker's order ID
            
        Returns:
            Current OrderStatus
        """
        ...
    
    def get_execution_reports(self, broker_order_id: str) -> List[ExecutionReport]:
        """
        Get all execution reports for an order.
        
        Args:
            broker_order_id: Broker's order ID
            
        Returns:
            List of ExecutionReport objects
        """
        ...
    
    def get_market_price(self, symbol: str) -> float:
        """
        Get current market price for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current market price
        """
        ...


class MockBrokerAdapter:
    """
    Mock broker adapter for testing and development.
    
    Simulates broker behavior:
    - Market orders: Immediate fill at market price
    - Limit orders: Fill if price matches
    - Stop orders: Convert to market when triggered
    """
    
    def __init__(self, fill_rate: float = 1.0, latency_ms: int = 100):
        self.fill_rate = fill_rate
        self.latency_ms = latency_ms
        self._orders: Dict[str, ExecutionReport] = {}
        self._market_prices: Dict[str, float] = {
            "600519": 1800.0,
            "000001": 12.5,
            "sh600036": 35.0,
            "sz000858": 180.0,
        }
    
    def submit_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: int,
        price: Optional[float],
    ) -> ExecutionReport:
        market_price = self.get_market_price(symbol)
        
        if order_type == "market":
            filled_qty = quantity if self.fill_rate >= 1.0 else int(quantity * self.fill_rate)
            return ExecutionReport(
                order_id=order_id,
                broker_order_id=f"MOCK-{order_id}",
                status=OrderStatus.FILLED if filled_qty == quantity else OrderStatus.PARTIAL_FILLED,
                filled_quantity=filled_qty,
                avg_fill_price=market_price,
                timestamp=datetime.now().isoformat(),
                message="Mock market order executed",
            )
        
        elif order_type == "limit":
            if price is None:
                return ExecutionReport(
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    reject_reason="Limit order requires price",
                    timestamp=datetime.now().isoformat(),
                )
            
            fill_condition = (side == "buy" and price >= market_price) or \
                            (side == "sell" and price <= market_price)
            
            if fill_condition:
                filled_qty = quantity if self.fill_rate >= 1.0 else int(quantity * self.fill_rate)
                return ExecutionReport(
                    order_id=order_id,
                    broker_order_id=f"MOCK-{order_id}",
                    status=OrderStatus.FILLED if filled_qty == quantity else OrderStatus.PARTIAL_FILLED,
                    filled_quantity=filled_qty,
                    avg_fill_price=price,
                    timestamp=datetime.now().isoformat(),
                    message="Mock limit order executed",
                )
            else:
                return ExecutionReport(
                    order_id=order_id,
                    broker_order_id=f"MOCK-{order_id}",
                    status=OrderStatus.PENDING,
                    filled_quantity=0,
                    avg_fill_price=0.0,
                    timestamp=datetime.now().isoformat(),
                    message="Mock limit order pending",
                )
        
        elif order_type == "stop":
            return ExecutionReport(
                order_id=order_id,
                broker_order_id=f"MOCK-{order_id}",
                status=OrderStatus.PENDING,
                filled_quantity=0,
                avg_fill_price=0.0,
                timestamp=datetime.now().isoformat(),
                message="Mock stop order pending",
            )
        
        else:
            return ExecutionReport(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                reject_reason=f"Unknown order type: {order_type}",
                timestamp=datetime.now().isoformat(),
            )
    
    def cancel_order(self, order_id: str, broker_order_id: Optional[str]) -> bool:
        return True
    
    def get_order_status(self, broker_order_id: str) -> OrderStatus:
        return OrderStatus.PENDING
    
    def get_execution_reports(self, broker_order_id: str) -> List[ExecutionReport]:
        return []
    
    def get_market_price(self, symbol: str) -> float:
        return self._market_prices.get(symbol, 100.0)
    
    def set_market_price(self, symbol: str, price: float) -> None:
        self._market_prices[symbol] = price