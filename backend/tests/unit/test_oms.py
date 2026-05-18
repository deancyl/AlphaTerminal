"""
Order Management System (OMS) Unit Tests

Tests all OMS components:
- OrderStatus state transitions
- OrderExecutionEngine lifecycle
- Pre-trade validation
- Broker adapter interface
"""

import pytest
import tempfile
import os
import sqlite3
from datetime import datetime

from app.services.oms.order_status import (
    OrderStatus,
    VALID_TRANSITIONS,
    is_valid_transition,
    get_allowed_transitions,
    is_terminal_status,
    get_active_statuses,
    get_terminal_statuses,
)
from app.services.oms.broker_adapter import MockBrokerAdapter, ExecutionReport
from app.services.oms.pre_trade_validation import PreTradeValidator, ValidationResult, ValidationError
from app.services.oms.order_engine import (
    OrderExecutionEngine,
    Order,
    InvalidStateTransitionError,
    OrderNotFoundError,
)


class TestOrderStatus:
    """Test OrderStatus enum and state transitions."""
    
    def test_status_values(self):
        assert OrderStatus.STAGED.value == "staged"
        assert OrderStatus.SUBMITTED.value == "submitted"
        assert OrderStatus.VALIDATED.value == "validated"
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.PARTIAL_FILLED.value == "partial"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"
        assert OrderStatus.REJECTED.value == "rejected"
        assert OrderStatus.EXPIRED.value == "expired"
    
    def test_valid_transitions_from_staged(self):
        assert is_valid_transition(OrderStatus.STAGED, OrderStatus.SUBMITTED)
        assert is_valid_transition(OrderStatus.STAGED, OrderStatus.CANCELLED)
        assert not is_valid_transition(OrderStatus.STAGED, OrderStatus.FILLED)
    
    def test_valid_transitions_from_submitted(self):
        assert is_valid_transition(OrderStatus.SUBMITTED, OrderStatus.VALIDATED)
        assert is_valid_transition(OrderStatus.SUBMITTED, OrderStatus.REJECTED)
        assert not is_valid_transition(OrderStatus.SUBMITTED, OrderStatus.FILLED)
    
    def test_valid_transitions_from_pending(self):
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.PARTIAL_FILLED)
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.FILLED)
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.CANCELLED)
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.EXPIRED)
        assert not is_valid_transition(OrderStatus.PENDING, OrderStatus.SUBMITTED)
    
    def test_valid_transitions_from_partial_filled(self):
        assert is_valid_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.FILLED)
        assert is_valid_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.CANCELLED)
        assert not is_valid_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.PENDING)
    
    def test_terminal_states_no_transitions(self):
        assert is_terminal_status(OrderStatus.FILLED)
        assert is_terminal_status(OrderStatus.CANCELLED)
        assert is_terminal_status(OrderStatus.REJECTED)
        assert is_terminal_status(OrderStatus.EXPIRED)
        
        assert not is_terminal_status(OrderStatus.STAGED)
        assert not is_terminal_status(OrderStatus.PENDING)
    
    def test_get_allowed_transitions(self):
        staged_transitions = get_allowed_transitions(OrderStatus.STAGED)
        assert OrderStatus.SUBMITTED in staged_transitions
        assert OrderStatus.CANCELLED in staged_transitions
        assert len(staged_transitions) == 2
        
        filled_transitions = get_allowed_transitions(OrderStatus.FILLED)
        assert len(filled_transitions) == 0
    
    def test_active_vs_terminal_statuses(self):
        active = get_active_statuses()
        terminal = get_terminal_statuses()
        
        assert OrderStatus.STAGED in active
        assert OrderStatus.PENDING in active
        assert OrderStatus.PARTIAL_FILLED in active
        
        assert OrderStatus.FILLED in terminal
        assert OrderStatus.CANCELLED in terminal
        
        assert active.isdisjoint(terminal)


class TestMockBrokerAdapter:
    """Test MockBrokerAdapter behavior."""
    
    def test_market_order_immediate_fill(self):
        broker = MockBrokerAdapter(fill_rate=1.0)
        report = broker.submit_order(
            order_id="test-1",
            symbol="600519",
            side="buy",
            order_type="market",
            quantity=100,
            price=None,
        )
        
        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == 100
        assert report.avg_fill_price > 0
        assert report.broker_order_id is not None
    
    def test_limit_order_fill_when_price_matches(self):
        broker = MockBrokerAdapter()
        broker.set_market_price("600519", 1800.0)
        
        report = broker.submit_order(
            order_id="test-2",
            symbol="600519",
            side="buy",
            order_type="limit",
            quantity=100,
            price=1850.0,  # Above market price
        )
        
        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == 100
        assert report.avg_fill_price == 1850.0
    
    def test_limit_order_pending_when_price_not_matched(self):
        broker = MockBrokerAdapter()
        broker.set_market_price("600519", 1800.0)
        
        report = broker.submit_order(
            order_id="test-3",
            symbol="600519",
            side="buy",
            order_type="limit",
            quantity=100,
            price=1700.0,  # Below market price
        )
        
        assert report.status == OrderStatus.PENDING
        assert report.filled_quantity == 0
    
    def test_limit_order_rejected_without_price(self):
        broker = MockBrokerAdapter()
        
        report = broker.submit_order(
            order_id="test-4",
            symbol="600519",
            side="buy",
            order_type="limit",
            quantity=100,
            price=None,
        )
        
        assert report.status == OrderStatus.REJECTED
        assert "requires price" in report.reject_reason.lower()
    
    def test_stop_order_pending(self):
        broker = MockBrokerAdapter()
        
        report = broker.submit_order(
            order_id="test-5",
            symbol="600519",
            side="buy",
            order_type="stop",
            quantity=100,
            price=1750.0,
        )
        
        assert report.status == OrderStatus.PENDING
    
    def test_cancel_order(self):
        broker = MockBrokerAdapter()
        result = broker.cancel_order("test-1", "MOCK-test-1")
        assert result is True
    
    def test_get_market_price(self):
        broker = MockBrokerAdapter()
        broker.set_market_price("600519", 1850.0)
        
        price = broker.get_market_price("600519")
        assert price == 1850.0
        
        unknown_price = broker.get_market_price("UNKNOWN")
        assert unknown_price == 100.0  # Default


class TestPreTradeValidator:
    """Test pre-trade validation logic."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        conn = sqlite3.connect(path)
        conn.execute("""
            CREATE TABLE portfolios (
                id INTEGER PRIMARY KEY,
                name TEXT,
                cash_balance REAL DEFAULT 0.0,
                initial_capital REAL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE position_summary (
                portfolio_id INTEGER,
                symbol TEXT,
                total_shares INTEGER DEFAULT 0,
                PRIMARY KEY (portfolio_id, symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE market_data_realtime (
                symbol TEXT PRIMARY KEY,
                price REAL
            )
        """)
        
        conn.execute("INSERT INTO portfolios (id, name, cash_balance, initial_capital) VALUES (1, 'Test', 100000.0, 50000.0)")
        conn.execute("INSERT INTO position_summary (portfolio_id, symbol, total_shares) VALUES (1, '600519', 200)")
        conn.execute("INSERT INTO market_data_realtime (symbol, price) VALUES ('600519', 1800.0)")
        conn.commit()
        conn.close()
        
        original_path = None
        try:
            from app.db import database
            original_path = database._db_path
            database._db_path = path
        except:
            pass
        
        yield path
        
        try:
            from app.db import database
            if original_path:
                database._db_path = original_path
        except:
            pass
        
        os.unlink(path)
    
    def test_validation_result_defaults(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
    
    def test_validation_result_add_error(self):
        result = ValidationResult(is_valid=True)
        result.add_error("TEST_ERROR", "Test error message", field="test_field")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "TEST_ERROR"
        assert result.errors[0].message == "Test error message"
        assert result.errors[0].field == "test_field"
    
    def test_validation_result_add_warning(self):
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        
        assert result.is_valid is True
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"


class TestOrderDataclass:
    """Test Order dataclass."""
    
    def test_order_creation(self):
        order = Order(
            id=1,
            portfolio_id=1,
            symbol="600519",
            side="buy",
            order_type="limit",
            quantity=100,
            price=1800.0,
            status=OrderStatus.STAGED,
        )
        
        assert order.id == 1
        assert order.symbol == "600519"
        assert order.side == "buy"
        assert order.quantity == 100
        assert order.price == 1800.0
        assert order.status == OrderStatus.STAGED
        assert order.filled_quantity == 0
        assert order.avg_fill_price == 0.0
    
    def test_order_to_dict(self):
        order = Order(
            id=1,
            portfolio_id=1,
            symbol="600519",
            side="buy",
            order_type="limit",
            quantity=100,
            price=1800.0,
            status=OrderStatus.STAGED,
        )
        
        d = order.to_dict()
        
        assert d["id"] == 1
        assert d["symbol"] == "600519"
        assert d["status"] == "staged"
        assert d["quantity"] == 100


class TestOrderExecutionEngine:
    """Test OrderExecutionEngine lifecycle."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        
        conn.execute("""
            CREATE TABLE portfolios (
                id INTEGER PRIMARY KEY,
                name TEXT,
                cash_balance REAL DEFAULT 0.0,
                initial_capital REAL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE position_summary (
                portfolio_id INTEGER,
                symbol TEXT,
                total_shares INTEGER DEFAULT 0,
                avg_cost REAL DEFAULT 0.0,
                PRIMARY KEY (portfolio_id, symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE position_lots (
                id INTEGER PRIMARY KEY,
                portfolio_id INTEGER,
                symbol TEXT,
                shares INTEGER,
                avg_cost REAL,
                buy_date TEXT,
                status TEXT DEFAULT 'open',
                realized_pnl REAL DEFAULT 0.0,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE market_data_realtime (
                symbol TEXT PRIMARY KEY,
                price REAL
            )
        """)
        conn.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL,
                status TEXT NOT NULL DEFAULT 'staged',
                filled_quantity INTEGER DEFAULT 0,
                avg_fill_price REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                submitted_at TEXT,
                filled_at TEXT,
                cancelled_at TEXT,
                reject_reason TEXT,
                broker_order_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                agent_id TEXT,
                action TEXT,
                resource TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                prev_hash TEXT,
                record_hash TEXT,
                chain_index INTEGER
            )
        """)
        
        conn.execute("INSERT INTO portfolios (id, name, cash_balance, initial_capital) VALUES (1, 'Test', 100000.0, 50000.0)")
        conn.execute("INSERT INTO position_summary (portfolio_id, symbol, total_shares, avg_cost) VALUES (1, '600519', 200, 1750.0)")
        conn.execute("INSERT INTO position_lots (portfolio_id, symbol, shares, avg_cost, buy_date, status, created_at) VALUES (1, '600519', 200, 1750.0, '2024-01-01', 'open', datetime('now'))")
        conn.execute("INSERT INTO market_data_realtime (symbol, price) VALUES ('600519', 1800.0)")
        conn.commit()
        conn.close()
        
        original_path = None
        try:
            from app.db import database
            original_path = database._db_path
            database._db_path = path
        except:
            pass
        
        yield path
        
        try:
            from app.db import database
            if original_path:
                database._db_path = original_path
        except:
            pass
        
        os.unlink(path)
    
    def test_create_order_validation(self, temp_db):
        broker = MockBrokerAdapter()
        oms = OrderExecutionEngine(broker_adapter=broker, enable_audit=False)
        
        with pytest.raises(ValueError, match="Invalid side"):
            oms.create_order(1, "600519", "invalid", 100, 1800.0)
        
        with pytest.raises(ValueError, match="Invalid order_type"):
            oms.create_order(1, "600519", "buy", 100, 1800.0, order_type="invalid")
        
        with pytest.raises(ValueError, match="Quantity must be positive"):
            oms.create_order(1, "600519", "buy", -100, 1800.0)
        
        with pytest.raises(ValueError, match="Limit order requires price"):
            oms.create_order(1, "600519", "buy", 100, None, order_type="limit")
    
    def test_cancel_invalid_state(self, temp_db):
        broker = MockBrokerAdapter()
        oms = OrderExecutionEngine(broker_adapter=broker, enable_audit=False)
        
        order = oms.create_order(1, "600519", "buy", 100, 1800.0)
        order.status = OrderStatus.FILLED
        oms._update_order(order)
        
        with pytest.raises(InvalidStateTransitionError):
            oms.cancel_order(order.id)
    
    def test_get_order_not_found(self, temp_db):
        broker = MockBrokerAdapter()
        oms = OrderExecutionEngine(broker_adapter=broker, enable_audit=False)
        
        order = oms.get_order(99999)
        assert order is None
    
    def test_process_fill_invalid_state(self, temp_db):
        broker = MockBrokerAdapter()
        oms = OrderExecutionEngine(broker_adapter=broker, enable_audit=False)
        
        order = oms.create_order(1, "600519", "buy", 100, 1800.0)
        
        with pytest.raises(InvalidStateTransitionError):
            oms.process_fill(order.id, 50, 1800.0)


class TestStateTransitions:
    """Test all state transition scenarios."""
    
    def test_staged_to_submitted_valid(self):
        assert is_valid_transition(OrderStatus.STAGED, OrderStatus.SUBMITTED)
    
    def test_staged_to_cancelled_valid(self):
        assert is_valid_transition(OrderStatus.STAGED, OrderStatus.CANCELLED)
    
    def test_staged_to_filled_invalid(self):
        assert not is_valid_transition(OrderStatus.STAGED, OrderStatus.FILLED)
    
    def test_pending_to_partial_filled_valid(self):
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.PARTIAL_FILLED)
    
    def test_pending_to_filled_valid(self):
        assert is_valid_transition(OrderStatus.PENDING, OrderStatus.FILLED)
    
    def test_partial_filled_to_filled_valid(self):
        assert is_valid_transition(OrderStatus.PARTIAL_FILLED, OrderStatus.FILLED)
    
    def test_filled_to_any_invalid(self):
        for status in OrderStatus:
            if status != OrderStatus.FILLED:
                assert not is_valid_transition(OrderStatus.FILLED, status)
    
    def test_cancelled_to_any_invalid(self):
        for status in OrderStatus:
            if status != OrderStatus.CANCELLED:
                assert not is_valid_transition(OrderStatus.CANCELLED, status)
    
    def test_rejected_to_any_invalid(self):
        for status in OrderStatus:
            if status != OrderStatus.REJECTED:
                assert not is_valid_transition(OrderStatus.REJECTED, status)


class TestExecutionReport:
    """Test ExecutionReport dataclass."""
    
    def test_execution_report_creation(self):
        report = ExecutionReport(
            order_id="test-1",
            broker_order_id="BROKER-1",
            status=OrderStatus.FILLED,
            filled_quantity=100,
            avg_fill_price=1800.0,
            commission=5.0,
            message="Order filled",
        )
        
        assert report.order_id == "test-1"
        assert report.broker_order_id == "BROKER-1"
        assert report.status == OrderStatus.FILLED
        assert report.filled_quantity == 100
        assert report.avg_fill_price == 1800.0
        assert report.commission == 5.0
    
    def test_execution_report_defaults(self):
        report = ExecutionReport(
            order_id="test-1",
            status=OrderStatus.PENDING,
        )
        
        assert report.filled_quantity == 0
        assert report.avg_fill_price == 0.0
        assert report.commission == 0.0
        assert report.broker_order_id is None
        assert report.message is None
        assert report.reject_reason is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])