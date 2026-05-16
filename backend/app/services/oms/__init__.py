"""
Order Management System (OMS) Module

This module provides a professional order management system with:
- OrderStatus enum with state machine transitions
- OrderExecutionEngine for order lifecycle management
- Pre-trade validation middleware
- Broker adapter interface for future integration

Components:
- order_status: OrderStatus enum and state transitions
- order_engine: OrderExecutionEngine class
- broker_adapter: Abstract broker interface (Protocol)
- pre_trade_validation: Validation middleware
"""

from .order_status import OrderStatus, VALID_TRANSITIONS, is_valid_transition
from .order_engine import OrderExecutionEngine, Order, ExecutionReport
from .broker_adapter import BrokerAdapter, MockBrokerAdapter
from .pre_trade_validation import PreTradeValidator, ValidationResult

__all__ = [
    # Order Status
    "OrderStatus",
    "VALID_TRANSITIONS",
    "is_valid_transition",
    # Order Engine
    "OrderExecutionEngine",
    "Order",
    "ExecutionReport",
    # Broker Adapter
    "BrokerAdapter",
    "MockBrokerAdapter",
    # Pre-trade Validation
    "PreTradeValidator",
    "ValidationResult",
]
