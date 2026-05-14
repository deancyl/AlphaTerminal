"""
Pytest configuration and shared fixtures for AlphaTerminal backend tests.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Generator
import sys
import os
import tempfile
import sqlite3

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary test database."""
    # Create temp database file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Initialize tables
    from app.db.database import init_tables
    import app.db.database as db_module
    
    # Save original path
    original_path = db_module._db_path
    
    # Set test database path
    db_module._db_path = path
    
    try:
        init_tables()
        yield path
    finally:
        # Restore original path
        db_module._db_path = original_path
        # Clean up
        if os.path.exists(path):
            os.unlink(path)


@pytest.fixture
def mock_db_connection():
    """Mock database connection fixture."""
    conn = Mock()
    conn.execute = Mock(return_value=Mock(
        fetchone=Mock(return_value=None),
        fetchall=Mock(return_value=[])
    ))
    conn.close = Mock()
    return conn


@pytest.fixture
def mock_http_response():
    """Mock HTTP response fixture."""
    response = Mock()
    response.status_code = 200
    response.json = Mock(return_value={})
    response.text = ""
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def sample_stock_data():
    """Sample stock data for testing."""
    return {
        "symbol": "000001",
        "name": "平安银行",
        "price": 10.5,
        "change_pct": 2.5,
        "volume": 1000000,
        "market_cap": 2000000000
    }


@pytest.fixture
def sample_portfolio_data():
    """Sample portfolio data for testing."""
    return {
        "id": 1,
        "name": "测试组合",
        "description": "用于测试的组合",
        "initial_capital": 100000.0,
        "created_at": "2024-01-01T00:00:00"
    }


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks after each test."""
    yield
    # Cleanup code here if needed


@pytest.fixture(scope="session")
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    return client


@pytest.fixture(scope="function")
def client():
    """Create a function-scoped test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client
