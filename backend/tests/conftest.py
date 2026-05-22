"""
Pytest configuration and shared fixtures for AlphaTerminal backend tests.
"""

import pytest
import asyncio
from unittest.mock import Mock
import sys
import os
import tempfile

# Disable rate limiting for all tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Proxy availability check
PROXY_AVAILABLE = bool(os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY"))


@pytest.fixture(scope="session")
def proxy_available():
    """Check if proxy is available for external API tests."""
    return PROXY_AVAILABLE


def pytest_collection_modifyitems(config, items):
    """Auto-skip proxy-dependent tests when proxy unavailable."""
    skip_proxy = pytest.mark.skip(
        reason="Proxy required but not available (set HTTP_PROXY or HTTPS_PROXY)"
    )

    for item in items:
        if "proxy" in item.keywords and not PROXY_AVAILABLE:
            item.add_marker(skip_proxy)


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
    fd, path = tempfile.mkstemp(suffix=".db")
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
    conn.execute = Mock(
        return_value=Mock(
            fetchone=Mock(return_value=None), fetchall=Mock(return_value=[])
        )
    )
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
        "market_cap": 2000000000,
    }


@pytest.fixture
def sample_portfolio_data():
    """Sample portfolio data for testing."""
    return {
        "id": 1,
        "name": "测试组合",
        "description": "用于测试的组合",
        "initial_capital": 100000.0,
        "created_at": "2024-01-01T00:00:00",
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


@pytest.fixture
def sample_agent_token():
    """Create sample agent token for testing."""
    from datetime import datetime, timedelta
    from app.services.agent.token_service import AgentToken, TokenScope

    return AgentToken(
        id="test-token-id",
        name="test-agent",
        token_prefix="AGT1_abc123",
        token_hash="test-hash-123",
        scopes=[TokenScope.READ, TokenScope.WRITE],
        markets=["*"],
        instruments=["*"],
        paper_only=True,
        rate_limit=120,
        expires_at=datetime.now() + timedelta(days=30),
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        is_active=True,
        access_count=5,
    )


@pytest.fixture
def restricted_agent_token():
    """Create token with restricted markets."""
    from datetime import datetime, timedelta
    from app.services.agent.token_service import AgentToken, TokenScope

    return AgentToken(
        id="restricted-token-id",
        name="restricted-agent",
        token_prefix="AGT1_xyz789",
        token_hash="restricted-hash-789",
        scopes=[TokenScope.READ],
        markets=["ASTOCK"],
        instruments=["000001", "600519"],
        paper_only=True,
        rate_limit=60,
        expires_at=datetime.now() + timedelta(days=7),
        created_at=datetime.now(),
        last_used_at=datetime.now(),
        is_active=True,
        access_count=2,
    )


@pytest.fixture
def mock_llm_config():
    """Mock LLM configuration for testing."""
    return {
        "provider": "openai",
        "model_id": "gpt-4",
        "api_key": "test-api-key",
        "base_url": "https://api.openai.com/v1",
        "max_concurrent": 5,
        "context_length": 8192,
    }


@pytest.fixture
def mock_model_config_service():
    """Mock ModelConfigService for testing."""
    service = Mock()
    service.get_model = Mock(
        return_value=Mock(
            provider="openai",
            model_id="gpt-4",
            api_key="test-api-key",
            base_url="https://api.openai.com/v1",
            enabled=True,
            is_default=True,
            max_concurrent=5,
            context_length=8192,
            metadata={},
        )
    )
    service.get_all_providers = Mock(return_value=["openai", "deepseek", "qianwen"])
    service.get_models_for_provider = Mock(return_value=["gpt-4", "gpt-3.5-turbo"])
    return service


@pytest.fixture
def mock_circuit_breaker():
    """Mock circuit breaker for testing."""
    cb = Mock()
    cb.is_available = Mock(return_value=True)
    cb.__enter__ = Mock(return_value=None)
    cb.__exit__ = Mock(return_value=False)
    cb.state = "closed"
    cb.failure_count = 0
    cb.reset = Mock()
    return cb


@pytest.fixture
def mock_news_data():
    """Mock news data for testing."""
    return [
        {
            "title": "测试新闻标题1",
            "content": "测试新闻内容1",
            "source": "eastmoney",
            "publish_time": "2024-01-15 10:30:00",
            "url": "http://example.com/news/1",
        },
        {
            "title": "测试新闻标题2",
            "content": "测试新闻内容2",
            "source": "sina",
            "publish_time": "2024-01-15 09:00:00",
            "url": "http://example.com/news/2",
        },
    ]


@pytest.fixture
def mock_forex_quote():
    """Mock forex quote for testing."""
    return {
        "symbol": "USDCNY",
        "name": "美元/人民币",
        "bid": 7.2450,
        "ask": 7.2460,
        "last": 7.2455,
        "change": 0.0050,
        "change_pct": 0.069,
        "high": 7.2500,
        "low": 7.2400,
        "timestamp": "2024-01-15T10:30:00",
    }


@pytest.fixture
def mock_options_chain():
    """Mock options chain data for testing."""
    return {
        "symbol": "IO2501",
        "calls": [
            {"strike": 3800, "bid": 120.5, "ask": 121.0, "iv": 0.18, "delta": 0.65},
            {"strike": 3850, "bid": 95.2, "ask": 95.8, "iv": 0.17, "delta": 0.55},
        ],
        "puts": [
            {"strike": 3800, "bid": 45.3, "ask": 45.8, "iv": 0.19, "delta": -0.35},
            {"strike": 3850, "bid": 68.5, "ask": 69.0, "iv": 0.18, "delta": -0.45},
        ],
        "underlying_price": 3825.5,
        "expiry": "2025-01-17",
    }
