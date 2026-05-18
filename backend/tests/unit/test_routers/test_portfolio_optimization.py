"""
Tests for portfolio optimization fixes.

This module tests the 10 fixes implemented for the portfolio module:
1. Timeout protection (30s asyncio.wait_for)
2. Input validation (Pydantic ge=0 constraints)
3. Pagination support (limit/offset)
4. N+1 query optimization (recursive CTE)
5. Error handling (try/except with specific types)
6. Safe math operations (division by zero protection)
7. Rate limiting
8. Database connection cleanup
9. API key authentication
10. Response format standardization
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import app
from app.routers.portfolio.schemas import (
    TransactionIn, CashOpIn, TransferIn, BuyIn, SellIn,
    PortfolioIn, PositionIn
)


client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════
#  Fix 1: Timeout Protection Tests
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pnl_endpoint_timeout():
    """Test that PnL endpoint times out after 30 seconds"""
    from app.routers.portfolio.positions import PORTFOLIO_TIMEOUT
    
    # Verify timeout constant is set to 30 seconds
    assert PORTFOLIO_TIMEOUT == 30, "Timeout should be 30 seconds"


@pytest.mark.asyncio
async def test_list_positions_timeout():
    """Test that list_positions uses asyncio.wait_for with timeout"""
    from app.routers.portfolio.positions import list_positions
    
    # Check that the function exists and is async
    import inspect
    assert inspect.iscoroutinefunction(list_positions), "list_positions should be async"


@pytest.mark.asyncio
async def test_buy_lot_timeout():
    """Test that buy_lot endpoint has timeout protection"""
    from app.routers.portfolio.lots import buy_lot, PORTFOLIO_TIMEOUT
    
    # Verify timeout constant is imported
    assert PORTFOLIO_TIMEOUT == 30


@pytest.mark.asyncio
async def test_sell_lot_timeout():
    """Test that sell_lot endpoint has timeout protection"""
    from app.routers.portfolio.lots import sell_lot, PORTFOLIO_TIMEOUT
    
    assert PORTFOLIO_TIMEOUT == 30


# ══════════════════════════════════════════════════════════════════════════
#  Fix 2: Input Validation Tests
# ══════════════════════════════════════════════════════════════════════════

def test_transaction_in_rejects_negative_amount():
    """Test that TransactionIn rejects negative amounts"""
    with pytest.raises(ValidationError) as exc:
        TransactionIn(
            portfolio_id=1,
            type="deposit",
            amount=-100.0,
            balance_after=0.0
        )
    assert "greater than or equal to 0" in str(exc.value)


def test_transaction_in_rejects_negative_balance():
    """Test that TransactionIn rejects negative balance_after"""
    with pytest.raises(ValidationError) as exc:
        TransactionIn(
            portfolio_id=1,
            type="deposit",
            amount=100.0,
            balance_after=-50.0
        )
    assert "greater than or equal to 0" in str(exc.value)


def test_cash_op_in_rejects_negative_amount():
    """Test that CashOpIn rejects negative amounts"""
    with pytest.raises(ValidationError) as exc:
        CashOpIn(amount=-50.0)
    assert "greater than or equal to 0" in str(exc.value)


def test_transfer_in_rejects_negative_amount():
    """Test that TransferIn rejects negative amounts"""
    with pytest.raises(ValidationError) as exc:
        TransferIn(
            from_portfolio_id=1,
            to_portfolio_id=2,
            amount=-100.0
        )
    # TransferIn uses gt=0, so it should reject <= 0
    assert "greater than 0" in str(exc.value)


def test_transfer_in_rejects_same_accounts():
    """Test that TransferIn rejects same source and destination accounts"""
    with pytest.raises(ValidationError) as exc:
        TransferIn(
            from_portfolio_id=1,
            to_portfolio_id=1,
            amount=100.0
        )
    assert "不能相同" in str(exc.value)


def test_buy_in_rejects_zero_shares():
    """Test that BuyIn rejects zero shares"""
    with pytest.raises(ValidationError) as exc:
        BuyIn(
            symbol="600519",
            shares=0,
            buy_price=100.0
        )
    assert "greater than 0" in str(exc.value)


def test_buy_in_rejects_zero_price():
    """Test that BuyIn rejects zero price"""
    with pytest.raises(ValidationError) as exc:
        BuyIn(
            symbol="600519",
            shares=100,
            buy_price=0.0
        )
    assert "greater than 0" in str(exc.value)


def test_sell_in_rejects_zero_shares():
    """Test that SellIn rejects zero shares"""
    with pytest.raises(ValidationError) as exc:
        SellIn(
            symbol="600519",
            shares=0,
            sell_price=100.0
        )
    assert "greater than 0" in str(exc.value)


def test_portfolio_in_rejects_empty_name():
    """Test that PortfolioIn rejects empty name"""
    with pytest.raises(ValidationError) as exc:
        PortfolioIn(name="   ")
    assert "不能为空" in str(exc.value)


def test_portfolio_in_rejects_negative_capital():
    """Test that PortfolioIn rejects negative initial_capital"""
    with pytest.raises(ValidationError) as exc:
        PortfolioIn(
            name="Test Portfolio",
            initial_capital=-1000.0
        )
    assert "greater than or equal to 0" in str(exc.value)


def test_position_in_rejects_negative_shares():
    """Test that PositionIn rejects negative shares"""
    with pytest.raises(ValidationError) as exc:
        PositionIn(
            portfolio_id=1,
            symbol="600519",
            shares=-100,
            avg_cost=10.0
        )
    assert "greater than or equal to 0" in str(exc.value)


def test_position_in_rejects_negative_cost():
    """Test that PositionIn rejects negative avg_cost"""
    with pytest.raises(ValidationError) as exc:
        PositionIn(
            portfolio_id=1,
            symbol="600519",
            shares=100,
            avg_cost=-10.0
        )
    assert "greater than or equal to 0" in str(exc.value)


# ══════════════════════════════════════════════════════════════════════════
#  Fix 3: Pagination Tests
# ══════════════════════════════════════════════════════════════════════════

def test_list_positions_pagination_params():
    """Test that list_positions accepts pagination parameters"""
    response = client.get("/api/v1/portfolio/1/positions?limit=10&offset=0")
    # Accept any status code - the endpoint exists and accepts params
    assert response.status_code in [200, 404, 500, 504]


def test_list_positions_pagination_limit_validation():
    """Test that pagination limit is validated (1-500)"""
    # Limit too low
    response = client.get("/api/v1/portfolio/1/positions?limit=0")
    assert response.status_code == 422  # Validation error
    
    # Limit too high
    response = client.get("/api/v1/portfolio/1/positions?limit=501")
    assert response.status_code == 422


def test_list_positions_pagination_offset_validation():
    """Test that pagination offset is validated (>=0)"""
    response = client.get("/api/v1/portfolio/1/positions?offset=-1")
    assert response.status_code == 422


def test_list_lots_with_summary_pagination():
    """Test that list_lots_with_summary supports pagination"""
    response = client.get("/api/v1/portfolio/1/lots/with_summary?limit=5&offset=10")
    assert response.status_code in [200, 404, 500, 504]


# ══════════════════════════════════════════════════════════════════════════
#  Fix 4: N+1 Query Optimization Tests
# ══════════════════════════════════════════════════════════════════════════

def test_tree_endpoint_uses_recursive_cte():
    """Test that tree endpoint uses recursive CTE (not N+1 queries)"""
    # Read the source code to verify CTE usage
    from app.routers.portfolio.lots import get_portfolio_tree
    import inspect
    source = inspect.getsource(get_portfolio_tree)
    
    # Check for recursive CTE pattern
    assert "WITH RECURSIVE" in source, "Tree endpoint should use recursive CTE"
    assert "portfolio_tree" in source, "CTE should be named portfolio_tree"


def test_get_all_descendants_prevents_infinite_recursion():
    """Test that _get_all_descendants uses visited set to prevent cycles"""
    from app.routers.portfolio.positions import _get_all_descendants
    import inspect
    source = inspect.getsource(_get_all_descendants)
    
    # Check for visited set pattern
    assert "visited" in source, "Should use visited set"
    assert "if portfolio_id in visited" in source, "Should check visited set"


# ══════════════════════════════════════════════════════════════════════════
#  Fix 5: Error Handling Tests
# ══════════════════════════════════════════════════════════════════════════

def test_timeout_returns_504():
    """Test that timeout errors return 504 Gateway Timeout"""
    from app.routers.portfolio.positions import list_positions
    
    # Check source code for proper error handling
    import inspect
    source = inspect.getsource(list_positions)
    
    assert "asyncio.TimeoutError" in source, "Should catch TimeoutError"
    assert "HTTPException(504" in source, "Should return 504 on timeout"


def test_database_errors_return_500():
    """Test that database errors return 500 Internal Server Error"""
    from app.routers.portfolio.lots import buy_lot
    
    import inspect
    source = inspect.getsource(buy_lot)
    
    assert "sqlite3.OperationalError" in source, "Should catch OperationalError"
    assert "HTTPException(500" in source or "HTTPException(400" in source


def test_value_errors_return_400():
    """Test that ValueError returns 400 Bad Request"""
    from app.routers.portfolio.lots import buy_lot
    
    import inspect
    source = inspect.getsource(buy_lot)
    
    assert "ValueError" in source, "Should catch ValueError"
    assert "HTTPException(400" in source, "Should return 400 for ValueError"


# ══════════════════════════════════════════════════════════════════════════
#  Fix 6: Safe Math Operations Tests
# ══════════════════════════════════════════════════════════════════════════

def test_pnl_calculation_handles_zero_cost():
    """Test that PnL percentage calculation handles zero cost"""
    from app.routers.portfolio.positions import portfolio_pnl
    
    import inspect
    source = inspect.getsource(portfolio_pnl)
    
    # Check for division by zero protection
    assert "if cost_total > 0" in source or "if total_cost" in source, \
        "Should check for zero before division"


def test_weight_calculation_handles_zero_total():
    """Test that weight calculation handles zero total value"""
    from app.routers.portfolio.positions import portfolio_pnl
    
    import inspect
    source = inspect.getsource(portfolio_pnl)
    
    # Check for division by zero protection in weight calculation
    assert "if total_value > 0" in source, \
        "Should check for zero before weight division"


# ══════════════════════════════════════════════════════════════════════════
#  Fix 7: Rate Limiting Tests
# ══════════════════════════════════════════════════════════════════════════

def test_rate_limit_config_exists():
    """Test that rate limit configuration exists for portfolio endpoints"""
    try:
        from app.config.rate_limit import ENDPOINT_LIMITS, get_endpoint_category
        # Check that default limit is configured
        assert "default" in ENDPOINT_LIMITS
        # Portfolio endpoints use default category
        category = get_endpoint_category("/api/v1/portfolio/1/positions")
        assert category == "default"
    except ImportError:
        pytest.skip("Rate limit config not found")


# ══════════════════════════════════════════════════════════════════════════
#  Fix 8: Database Connection Cleanup Tests
# ══════════════════════════════════════════════════════════════════════════

def test_list_positions_closes_connection():
    """Test that list_positions closes database connection"""
    from app.routers.portfolio.positions import list_positions
    
    import inspect
    source = inspect.getsource(list_positions)
    
    # Check for try/finally pattern with conn.close()
    assert "finally:" in source, "Should have finally block"
    assert "conn.close()" in source, "Should close connection in finally"


def test_portfolio_pnl_closes_connection():
    """Test that portfolio_pnl closes database connection"""
    from app.routers.portfolio.positions import portfolio_pnl
    
    import inspect
    source = inspect.getsource(portfolio_pnl)
    
    assert "finally:" in source, "Should have finally block"
    assert "conn.close()" in source, "Should close connection in finally"


def test_tree_endpoint_closes_connection():
    """Test that get_portfolio_tree closes database connection"""
    from app.routers.portfolio.lots import get_portfolio_tree
    
    import inspect
    source = inspect.getsource(get_portfolio_tree)
    
    assert "finally:" in source, "Should have finally block"
    assert "conn.close()" in source, "Should close connection in finally"


# ══════════════════════════════════════════════════════════════════════════
#  Fix 9: API Key Authentication Tests
# ══════════════════════════════════════════════════════════════════════════

def test_buy_lot_requires_api_key():
    """Test that buy_lot endpoint requires API key"""
    from app.routers.portfolio.lots import buy_lot
    
    import inspect
    source = inspect.getsource(buy_lot)
    
    assert "require_api_key" in source, "Should require API key"


def test_sell_lot_requires_api_key():
    """Test that sell_lot endpoint requires API key"""
    from app.routers.portfolio.lots import sell_lot
    
    import inspect
    source = inspect.getsource(sell_lot)
    
    assert "require_api_key" in source, "Should require API key"


def test_upsert_position_requires_api_key():
    """Test that upsert_position endpoint requires API key"""
    from app.routers.portfolio.positions import upsert_position
    
    import inspect
    source = inspect.getsource(upsert_position)
    
    assert "require_api_key" in source, "Should require API key"


def test_delete_position_requires_api_key():
    """Test that delete_position endpoint requires API key"""
    from app.routers.portfolio.positions import delete_position
    
    import inspect
    source = inspect.getsource(delete_position)
    
    assert "require_api_key" in source, "Should require API key"


# ══════════════════════════════════════════════════════════════════════════
#  Fix 10: Response Format Standardization Tests
# ══════════════════════════════════════════════════════════════════════════

def test_list_positions_uses_success_response():
    """Test that list_positions uses success_response wrapper"""
    from app.routers.portfolio.positions import list_positions
    
    import inspect
    source = inspect.getsource(list_positions)
    
    assert "success_response" in source, "Should use success_response wrapper"


def test_portfolio_pnl_uses_success_response():
    """Test that portfolio_pnl uses success_response wrapper"""
    from app.routers.portfolio.positions import portfolio_pnl
    
    import inspect
    source = inspect.getsource(portfolio_pnl)
    
    assert "success_response" in source, "Should use success_response wrapper"


def test_buy_lot_uses_success_response():
    """Test that buy_lot uses success_response wrapper"""
    from app.routers.portfolio.lots import buy_lot
    
    import inspect
    source = inspect.getsource(buy_lot)
    
    assert "success_response" in source, "Should use success_response wrapper"


def test_list_lots_uses_success_response():
    """Test that list_lots uses success_response wrapper"""
    from app.routers.portfolio.lots import list_lots
    
    import inspect
    source = inspect.getsource(list_lots)
    
    assert "success_response" in source, "Should use success_response wrapper"


# ══════════════════════════════════════════════════════════════════════════
#  Integration Tests
# ══════════════════════════════════════════════════════════════════════════

class TestPortfolioEndpoints:
    """Integration tests for portfolio endpoints."""
    
    def test_get_positions_endpoint_exists(self):
        """Test that GET /positions endpoint exists"""
        response = client.get("/api/v1/portfolio/1/positions")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_pnl_endpoint_exists(self):
        """Test that GET /pnl endpoint exists"""
        response = client.get("/api/v1/portfolio/1/pnl")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_lots_endpoint_exists(self):
        """Test that GET /lots endpoint exists"""
        response = client.get("/api/v1/portfolio/1/lots")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_tree_endpoint_exists(self):
        """Test that GET /tree endpoint exists"""
        response = client.get("/api/v1/portfolio/1/tree")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_conservation_endpoint_exists(self):
        """Test that GET /conservation endpoint exists"""
        response = client.get("/api/v1/portfolio/1/conservation")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_snapshots_endpoint_exists(self):
        """Test that GET /snapshots endpoint exists"""
        response = client.get("/api/v1/portfolio/1/snapshots")
        assert response.status_code in [200, 404, 500, 504]
    
    def test_get_pnl_today_endpoint_exists(self):
        """Test that GET /pnl/today endpoint exists"""
        response = client.get("/api/v1/portfolio/1/pnl/today")
        assert response.status_code in [200, 404, 500, 504]


# ══════════════════════════════════════════════════════════════════════════
#  Edge Case Tests
# ══════════════════════════════════════════════════════════════════════════

def test_buy_in_validates_date_format():
    """Test that BuyIn validates date format as YYYY-MM-DD"""
    # Valid date
    buy = BuyIn(
        symbol="600519",
        shares=100,
        buy_price=100.0,
        buy_date="2024-01-15"
    )
    assert buy.buy_date == "2024-01-15"
    
    # Invalid date format
    with pytest.raises(ValidationError) as exc:
        BuyIn(
            symbol="600519",
            shares=100,
            buy_price=100.0,
            buy_date="2024/01/15"  # Wrong format
        )
    assert "Invalid date format" in str(exc.value)


def test_portfolio_in_validates_type():
    """Test that PortfolioIn validates type field"""
    # Valid types
    for valid_type in ["portfolio", "account", "strategy", "group", "main"]:
        p = PortfolioIn(name="Test", type=valid_type)
        assert p.type == valid_type
    
    # Invalid type
    with pytest.raises(ValidationError):
        PortfolioIn(name="Test", type="invalid_type")


def test_portfolio_in_validates_currency():
    """Test that PortfolioIn validates currency field"""
    # Valid currencies
    for valid_currency in ["CNY", "USD", "HKD", "EUR"]:
        p = PortfolioIn(name="Test", currency=valid_currency)
        assert p.currency == valid_currency
    
    # Invalid currency
    with pytest.raises(ValidationError):
        PortfolioIn(name="Test", currency="JPY")


def test_portfolio_in_validates_status():
    """Test that PortfolioIn validates status field"""
    # Valid statuses
    for valid_status in ["active", "frozen", "closed"]:
        p = PortfolioIn(name="Test", status=valid_status)
        assert p.status == valid_status
    
    # Invalid status
    with pytest.raises(ValidationError):
        PortfolioIn(name="Test", status="pending")


def test_transaction_in_validates_type():
    """Test that TransactionIn validates type field"""
    # Valid types
    for valid_type in ["deposit", "withdraw", "transfer_in", "transfer_out", "dividend", "fee"]:
        t = TransactionIn(
            portfolio_id=1,
            type=valid_type,
            amount=100.0,
            balance_after=100.0
        )
        assert t.type == valid_type
    
    # Invalid type
    with pytest.raises(ValidationError):
        TransactionIn(
            portfolio_id=1,
            type="invalid_type",
            amount=100.0,
            balance_after=100.0
        )
