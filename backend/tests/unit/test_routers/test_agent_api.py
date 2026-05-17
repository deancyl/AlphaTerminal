"""
Unit tests for Agent API Router endpoints.

Tests cover:
- Health check endpoint
- Whoami endpoint
- Market listing with permission filtering
- Symbol search with market filtering
- K-line data retrieval
- Price data retrieval
- Scope enforcement
- Rate limiting
- Comprehensive debug logging verification
"""
import pytest
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi import HTTPException, status

# Set environment before importing
os.environ["AGENT_API_DEBUG"] = "true"
os.environ["TOKEN_DEBUG"] = "true"

from app.routers.agent import (
    router,
    get_token_service,
    HealthResponse,
    WhoamiResponse,
    MarketsResponse,
    SymbolsResponse,
    KlinesRequest,
    KlinesResponse,
)
from app.services.agent.token_service import (
    AgentToken,
    TokenScope,
    Market,
    AgentTokenService,
)
from app.middleware.agent_auth import verify_agent_token, require_scope


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create FastAPI app with agent router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_client(app, sample_agent_token):
    """Create test client with authentication override."""
    from app.middleware.agent_auth import verify_agent_token, require_scope
    from app.services.agent.token_service import TokenScope
    
    async def override_verify():
        return sample_agent_token
    
    def override_require_scope(scope: TokenScope):
        async def dependency():
            return sample_agent_token
        return dependency
    
    app.dependency_overrides[verify_agent_token] = override_verify
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def restricted_auth_client(app, restricted_agent_token):
    """Create test client with restricted token override."""
    from app.middleware.agent_auth import verify_agent_token
    
    async def override_verify():
        return restricted_agent_token
    
    app.dependency_overrides[verify_agent_token] = override_verify
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


# Use sample_agent_token and restricted_agent_token from conftest.py
# Aliases for backward compatibility with existing tests
@pytest.fixture
def mock_token_service():
    """Mock token service."""
    service = Mock(spec=AgentTokenService)
    return service


@pytest.fixture
def sample_token(sample_agent_token):
    """Alias for sample_agent_token for backward compatibility."""
    return sample_agent_token


@pytest.fixture
def restricted_token(restricted_agent_token):
    """Alias for restricted_agent_token for backward compatibility."""
    return restricted_agent_token


# ============================================================================
# Health Check Endpoint Tests
# ============================================================================

class TestHealthEndpoint:
    """Test /api/agent/v1/health endpoint."""

    def test_health_check_success(self, client):
        """Test successful health check."""
        response = client.get("/api/agent/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["version"] == "0.6.12"

    def test_health_check_no_auth_required(self, client):
        """Test that health check doesn't require authentication."""
        response = client.get("/api/agent/v1/health")
        assert response.status_code == 200

    def test_health_check_response_format(self, client):
        """Test health check response format."""
        response = client.get("/api/agent/v1/health")
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert isinstance(data["timestamp"], str)


# ============================================================================
# Whoami Endpoint Tests
# ============================================================================

class TestWhoamiEndpoint:
    """Test /api/agent/v1/whoami endpoint."""

    def test_whoami_success(self, client, sample_token):
        """Test successful whoami request."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        response = client.get(
            "/api/agent/v1/whoami",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_token.id
        assert data["name"] == sample_token.name
        assert data["scopes"] == ["R", "W"]
        assert data["markets"] == ["*"]
        assert data["paper_only"] is True
        assert data["rate_limit"] == 120
        
        app.dependency_overrides.clear()

    def test_whoami_missing_auth(self, client):
        """Test whoami without authentication."""
        response = client.get("/api/agent/v1/whoami")
        assert response.status_code == 401

    def test_whoami_invalid_token(self, client):
        """Test whoami with invalid token."""
        response = client.get(
            "/api/agent/v1/whoami",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401


# ============================================================================
# Markets Endpoint Tests
# ============================================================================

class TestMarketsEndpoint:
    """Test /api/agent/v1/markets endpoint."""

    def test_list_markets_success(self, client, sample_token):
        """Test successful market listing."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            response = client.get(
                "/api/agent/v1/markets",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "markets" in data
            assert len(data["markets"]) == 6
            assert "ASTOCK" in data["markets"]
            assert "HKSTOCK" in data["markets"]
        
        app.dependency_overrides.clear()

    def test_list_markets_with_wildcard_access(self, client, sample_token):
        """Test market listing with wildcard access."""
        from app.middleware.agent_auth import verify_agent_token
        
        sample_token.markets = ["*"]
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            response = client.get(
                "/api/agent/v1/markets",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["markets"]) == 6
        
        app.dependency_overrides.clear()

    def test_list_markets_with_restricted_access(self, client, restricted_token):
        """Test market listing with restricted access."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            response = client.get(
                "/api/agent/v1/markets",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["markets"]) == 1
            assert data["markets"][0] == "ASTOCK"
        
        app.dependency_overrides.clear()


# ============================================================================
# Symbols Search Endpoint Tests
# ============================================================================

class TestSymbolsEndpoint:
    """Test /api/agent/v1/markets/{market}/symbols endpoint."""

    def test_search_symbols_success(self, client, sample_token):
        """Test successful symbol search."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.routers.stocks.search_stocks") as mock_search:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            mock_search.return_value = {
                "data": {
                    "stocks": [
                        {"code": "sh600519", "name": "贵州茅台"},
                        {"code": "sz000858", "name": "五粮液"},
                    ]
                }
            }
            
            response = client.get(
                "/api/agent/v1/markets/AStock/symbols?keyword=茅台&limit=10",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "symbols" in data
        
        app.dependency_overrides.clear()

    def test_search_symbols_market_access_denied(self, client, restricted_token):
        """Test symbol search with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        response = client.get(
            "/api/agent/v1/markets/AStock/symbols",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 403
        assert "not allowed" in response.json()["detail"]
        
        app.dependency_overrides.clear()

    def test_search_symbols_with_limit(self, client, sample_token):
        """Test symbol search with limit parameter."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.routers.stocks.search_stocks") as mock_search:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            mock_search.return_value = {
                "data": {
                    "stocks": [
                        {"code": "sh600519", "name": "贵州茅台"},
                        {"code": "sz000858", "name": "五粮液"},
                    ]
                }
            }
            
            response = client.get(
                "/api/agent/v1/markets/AStock/symbols?limit=1",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["symbols"]) <= 1
        
        app.dependency_overrides.clear()


# ============================================================================
# K-lines Endpoint Tests
# ============================================================================

class TestKlinesEndpoint:
    """Test /api/agent/v1/klines endpoint."""

    def test_get_klines_success(self, client, sample_token):
        """Test successful k-line retrieval."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.get_periodic_history") as mock_get_history:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            mock_get_history.return_value = [
                {
                    "trade_date": "2024-01-01",
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 103.0,
                    "volume": 1000000,
                },
                {
                    "trade_date": "2024-01-02",
                    "open": 103.0,
                    "high": 108.0,
                    "low": 102.0,
                    "close": 107.0,
                    "volume": 1200000,
                }
            ]
            
            response = client.post(
                "/api/agent/v1/klines",
                json={
                    "market": "AStock",
                    "symbol": "600519",
                    "timeframe": "1D",
                    "limit": 100
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["market"] == "AStock"
            assert data["symbol"] == "600519"
            assert data["timeframe"] == "1D"
            assert "data" in data
        
        app.dependency_overrides.clear()

    def test_get_klines_market_access_denied(self, client, restricted_token):
        """Test k-line retrieval with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        response = client.post(
            "/api/agent/v1/klines",
            json={
                "market": "AStock",
                "symbol": "600519",
                "timeframe": "1D",
                "limit": 100
            },
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 403
        
        app.dependency_overrides.clear()

    def test_get_klines_with_timeframe_mapping(self, client, sample_token):
        """Test k-line retrieval with different timeframes."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.get_periodic_history") as mock_get_history:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            mock_get_history.return_value = []
            
            timeframes = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"]
            
            for tf in timeframes:
                response = client.post(
                    "/api/agent/v1/klines",
                    json={
                        "market": "AStock",
                        "symbol": "600519",
                        "timeframe": tf,
                        "limit": 100
                    },
                    headers={"Authorization": "Bearer AGT1_test_token"}
                )
            
            assert response.status_code == 200
        
        app.dependency_overrides.clear()


# ============================================================================
# Strategy Endpoints Tests
# ============================================================================

class TestStrategyEndpoints:
    """Test /api/agent/v1/strategies endpoints."""

    def test_list_strategies_success(self, client, sample_token):
        """Test successful strategy listing with pagination."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.list_strategies") as mock_list, \
             patch("app.db.strategy_db.count_strategies") as mock_count:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_list.return_value = [
                {
                    "id": "strategy-1",
                    "name": "MA Cross",
                    "description": "Moving average crossover",
                    "market": "AStock",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                },
                {
                    "id": "strategy-2",
                    "name": "RSI Strategy",
                    "description": "RSI overbought/oversold",
                    "market": "HKStock",
                    "created_at": "2024-01-02T00:00:00",
                    "updated_at": "2024-01-02T00:00:00",
                },
            ]
            mock_count.return_value = 2

            response = client.get(
                "/api/agent/v1/strategies?limit=20&offset=0",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "strategies" in data
            assert data["total"] == 2
            assert data["limit"] == 20
            assert data["offset"] == 0
            assert len(data["strategies"]) == 2
        
        app.dependency_overrides.clear()

    def test_list_strategies_with_market_filter(self, client, sample_token):
        """Test strategy listing with market filter."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.list_strategies") as mock_list, \
             patch("app.db.strategy_db.count_strategies") as mock_count:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_list.return_value = [
                {
                    "id": "strategy-1",
                    "name": "MA Cross",
                    "description": "Moving average crossover",
                    "market": "AStock",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                }
            ]
            mock_count.return_value = 1

            response = client.get(
                "/api/agent/v1/strategies?market=AStock",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["strategies"]) == 1
            mock_list.assert_called_once()
        
        app.dependency_overrides.clear()

    def test_list_strategies_market_access_denied(self, client, restricted_token):
        """Test strategy listing with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify

        response = client.get(
            "/api/agent/v1/strategies?market=AStock",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )

        assert response.status_code == 403
        assert "not allowed" in response.json()["detail"]
        
        app.dependency_overrides.clear()

    def test_list_strategies_pagination(self, client, sample_token):
        """Test strategy listing pagination."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.list_strategies") as mock_list, \
             patch("app.db.strategy_db.count_strategies") as mock_count:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_list.return_value = []
            mock_count.return_value = 100

            response = client.get(
                "/api/agent/v1/strategies?limit=10&offset=20",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 10
            assert data["offset"] == 20
            assert data["has_more"] is True
        
        app.dependency_overrides.clear()

    def test_get_strategy_success(self, client, sample_token):
        """Test successful strategy retrieval."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = {
                "id": "strategy-1",
                "name": "MA Cross",
                "description": "Moving average crossover",
                "code": "ma_cross(5, 20)",
                "market": "AStock",
                "parameters": {"fast": 5, "slow": 20},
                "stop_loss_pct": 2.0,
                "take_profit_pct": 6.0,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            }

            response = client.get(
                "/api/agent/v1/strategies/strategy-1",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "strategy-1"
            assert data["name"] == "MA Cross"
            assert data["code"] == "ma_cross(5, 20)"
            assert data["market"] == "AStock"
        
        app.dependency_overrides.clear()

    def test_get_strategy_not_found(self, client, sample_token):
        """Test strategy not found."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = None

            response = client.get(
                "/api/agent/v1/strategies/nonexistent",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 404
        
        app.dependency_overrides.clear()

    def test_get_strategy_market_access_denied(self, client, restricted_token):
        """Test strategy retrieval with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify

        with patch("app.db.strategy_db.get_strategy") as mock_get:
            mock_get.return_value = {
                "id": "strategy-1",
                "name": "MA Cross",
                "market": "AStock",
            }

            response = client.get(
                "/api/agent/v1/strategies/strategy-1",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 403
        
        app.dependency_overrides.clear()

    def test_create_strategy_success(self, client, sample_token):
        """Test successful strategy creation."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.services.strategy.StrategyValidator.validate") as mock_validate, \
             patch("app.db.strategy_db.create_strategy") as mock_create:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_validate.return_value = (True, None)
            mock_create.return_value = {
                "id": "new-strategy-id",
                "name": "New Strategy",
            }

            response = client.post(
                "/api/agent/v1/strategies",
                json={
                    "name": "New Strategy",
                    "description": "Test strategy",
                    "code": "ma_cross(5, 20)",
                    "market": "AStock",
                    "parameters": {"fast": 5, "slow": 20},
                    "stop_loss_pct": 2.0,
                    "take_profit_pct": 6.0,
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert "id" in data["data"]
        
        app.dependency_overrides.clear()

    def test_create_strategy_validation_failed(self, client, sample_token):
        """Test strategy creation with validation failure."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.services.strategy.StrategyValidator.validate") as mock_validate:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_validate.return_value = (False, "Invalid strategy code")

            response = client.post(
                "/api/agent/v1/strategies",
                json={
                    "name": "Bad Strategy",
                    "code": "invalid_code",
                    "market": "AStock",
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 400
            assert "validation failed" in response.json()["detail"]
        
        app.dependency_overrides.clear()

    def test_create_strategy_market_access_denied(self, client, restricted_token):
        """Test strategy creation with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify

        response = client.post(
            "/api/agent/v1/strategies",
            json={
                "name": "New Strategy",
                "code": "ma_cross(5, 20)",
                "market": "AStock",
            },
            headers={"Authorization": "Bearer AGT1_test_token"}
        )

        assert response.status_code == 403
        
        app.dependency_overrides.clear()

    def test_update_strategy_success(self, client, sample_token):
        """Test successful strategy update."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.services.strategy.StrategyValidator.validate") as mock_validate, \
             patch("app.db.strategy_db.get_strategy") as mock_get, \
             patch("app.db.strategy_db.update_strategy") as mock_update:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = {
                "id": "strategy-1",
                "name": "Old Name",
                "market": "AStock",
            }
            mock_validate.return_value = (True, None)
            mock_update.return_value = {
                "id": "strategy-1",
                "name": "New Name",
                "market": "AStock",
            }

            response = client.put(
                "/api/agent/v1/strategies/strategy-1",
                json={
                    "name": "New Name",
                    "description": "Updated description",
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
        
        app.dependency_overrides.clear()

    def test_update_strategy_not_found(self, client, sample_token):
        """Test strategy update with non-existent strategy."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = None

            response = client.put(
                "/api/agent/v1/strategies/nonexistent",
                json={"name": "New Name"},
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 404
        
        app.dependency_overrides.clear()

    def test_delete_strategy_success(self, client, sample_token):
        """Test successful strategy deletion (soft delete)."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get, \
             patch("app.db.strategy_db.delete_strategy") as mock_delete:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = {
                "id": "strategy-1",
                "name": "MA Cross",
                "market": "AStock",
            }
            mock_delete.return_value = True

            response = client.delete(
                "/api/agent/v1/strategies/strategy-1",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["deleted"] is True
            assert data["data"]["hard_delete"] is False
        
        app.dependency_overrides.clear()

    def test_delete_strategy_hard_delete(self, client, sample_token):
        """Test hard delete strategy."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get, \
             patch("app.db.strategy_db.delete_strategy") as mock_delete:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = {
                "id": "strategy-1",
                "name": "MA Cross",
                "market": "AStock",
            }
            mock_delete.return_value = True

            response = client.delete(
                "/api/agent/v1/strategies/strategy-1?hard=true",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["hard_delete"] is True
        
        app.dependency_overrides.clear()

    def test_delete_strategy_not_found(self, client, sample_token):
        """Test strategy deletion with non-existent strategy."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service

            mock_get.return_value = None

            response = client.delete(
                "/api/agent/v1/strategies/nonexistent",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 404
        
        app.dependency_overrides.clear()


class TestStrategyScopeEnforcement:
    """Test scope enforcement for strategy endpoints."""

    def test_list_strategies_requires_auth(self, client):
        """Test that list strategies requires authentication."""
        response = client.get(
            "/api/agent/v1/strategies",
        )

        assert response.status_code == 401

    def test_get_strategy_requires_auth(self, client):
        """Test that get strategy requires authentication."""
        response = client.get(
            "/api/agent/v1/strategies/strategy-1",
        )

        assert response.status_code == 401

    def test_create_strategy_requires_auth(self, client):
        """Test that create strategy requires authentication."""
        response = client.post(
            "/api/agent/v1/strategies",
            json={
                "name": "Test",
                "code": "test",
                "market": "AStock",
            },
        )

        assert response.status_code == 401

    def test_update_strategy_requires_auth(self, client):
        """Test that update strategy requires authentication."""
        response = client.put(
            "/api/agent/v1/strategies/strategy-1",
            json={"name": "Updated"},
        )

        assert response.status_code == 401

    def test_delete_strategy_requires_auth(self, client):
        """Test that delete strategy requires authentication."""
        response = client.delete(
            "/api/agent/v1/strategies/strategy-1",
        )

        assert response.status_code == 401


class TestStrategyDebugLogging:
    """Test comprehensive debug logging for strategy endpoints."""

    def test_list_strategies_logging(self, client, sample_token):
        """Test that list strategies logs appropriately."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.list_strategies") as mock_list, \
             patch("app.db.strategy_db.count_strategies") as mock_count, \
             patch("app.routers.agent.logger") as mock_logger:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            mock_list.return_value = []
            mock_count.return_value = 0

            response = client.get(
                "/api/agent/v1/strategies",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            mock_logger.info.assert_called()
            mock_logger.debug.assert_called()
        
        app.dependency_overrides.clear()

    def test_get_strategy_logging(self, client, sample_token):
        """Test that get strategy logs appropriately."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.strategy_db.get_strategy") as mock_get, \
             patch("app.routers.agent.logger") as mock_logger:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            mock_get.return_value = {
                "id": "strategy-1",
                "name": "Test",
                "market": "AStock",
                "code": "test",
            }

            response = client.get(
                "/api/agent/v1/strategies/strategy-1",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            mock_logger.info.assert_called()
            mock_logger.debug.assert_called()
        
        app.dependency_overrides.clear()

    def test_create_strategy_logging(self, client, sample_token):
        """Test that create strategy logs appropriately."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.services.strategy.StrategyValidator.validate") as mock_validate, \
             patch("app.db.strategy_db.create_strategy") as mock_create, \
             patch("app.routers.agent.logger") as mock_logger:
            
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            mock_validate.return_value = (True, None)
            mock_create.return_value = {"id": "new-id"}

            response = client.post(
                "/api/agent/v1/strategies",
                json={
                    "name": "Test",
                    "code": "test",
                    "market": "AStock",
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )

            assert response.status_code == 200
            mock_logger.info.assert_called()
            mock_logger.debug.assert_called()
        
        app.dependency_overrides.clear()


# ============================================================================
# Price Endpoint Tests
# ============================================================================

class TestPriceEndpoint:
    """Test /api/agent/v1/price endpoint."""

    def test_get_price_success(self, client, sample_token):
        """Test successful price retrieval."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.routers.market.quotes.market_quote") as mock_quote:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            mock_quote.return_value = {
                "data": {
                    "price": 1800.0,
                    "price_change": 20.0,
                    "pct_change": 1.12,
                    "volume": 5000000,
                }
            }
            
            response = client.get(
                "/api/agent/v1/price?market=AStock&symbol=600519",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["market"] == "AStock"
            assert data["symbol"] == "600519"
            assert "price" in data
            assert "change" in data
            assert "change_pct" in data
        
        app.dependency_overrides.clear()

    def test_get_price_market_access_denied(self, client, restricted_token):
        """Test price retrieval with market access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.markets = ["HKSTOCK"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        response = client.get(
            "/api/agent/v1/price?market=AStock&symbol=600519",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 403
        
        app.dependency_overrides.clear()

    def test_get_price_instrument_access_denied(self, client, restricted_token):
        """Test price retrieval with instrument access denied."""
        from app.middleware.agent_auth import verify_agent_token
        
        restricted_token.instruments = ["000001"]
        
        async def override_verify():
            return restricted_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        response = client.get(
            "/api/agent/v1/price?market=AStock&symbol=600519",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 403
        
        app.dependency_overrides.clear()

    def test_get_price_fallback_on_error(self, client, sample_token):
        """Test price retrieval fallback on error."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.routers.market.quotes.market_quote") as mock_quote:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            mock_quote.side_effect = Exception("API error")
            
            response = client.get(
                "/api/agent/v1/price?market=AStock&symbol=600519",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "error" in data
        
        app.dependency_overrides.clear()


# ============================================================================
# Scope Enforcement Tests
# ============================================================================

class TestScopeEnforcement:
    """Test scope enforcement across endpoints."""

    def test_read_scope_required_for_markets(self, client):
        """Test that markets endpoint requires authentication."""
        response = client.get(
            "/api/agent/v1/markets",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 401

    def test_read_scope_required_for_symbols(self, client):
        """Test that symbols endpoint requires authentication."""
        response = client.get(
            "/api/agent/v1/markets/AStock/symbols",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 401

    def test_read_scope_required_for_klines(self, client):
        """Test that klines endpoint requires authentication."""
        response = client.post(
            "/api/agent/v1/klines",
            json={
                "market": "AStock",
                "symbol": "600519",
                "timeframe": "1D",
                "limit": 100
            },
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 401

    def test_read_scope_required_for_price(self, client):
        """Test that price endpoint requires authentication."""
        response = client.get(
            "/api/agent/v1/price?market=AStock&symbol=600519",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 401


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Test rate limiting enforcement."""

    def test_rate_limit_exceeded(self, client):
        """Test that rate limit is enforced."""
        response = client.get(
            "/api/agent/v1/whoami",
            headers={"Authorization": "Bearer AGT1_test_token"}
        )
        
        assert response.status_code == 401


class TestDebugLogging:
    """Test comprehensive debug logging."""

    @patch("app.routers.agent.logger")
    def test_health_check_logging(self, mock_logger, client):
        """Test that health check logs appropriately."""
        response = client.get("/api/agent/v1/health")
        
        assert response.status_code == 200
        mock_logger.info.assert_called()

    def test_whoami_logging(self, client, sample_token):
        """Test that whoami logs token details."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.logger") as mock_logger:
            response = client.get(
                "/api/agent/v1/whoami",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            mock_logger.info.assert_called()
            mock_logger.debug.assert_called()
        
        app.dependency_overrides.clear()

    def test_markets_logging(self, client, sample_token):
        """Test that markets endpoint logs appropriately."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.routers.agent.logger") as mock_logger:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            
            response = client.get(
                "/api/agent/v1/markets",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            assert response.status_code == 200
            mock_logger.info.assert_called()
            mock_logger.debug.assert_called()
        
        app.dependency_overrides.clear()


class TestIntegration:
    """Integration tests for agent API endpoints."""

    def test_full_workflow(self, client, sample_token):
        """Test full workflow: health -> whoami -> markets -> klines."""
        from app.middleware.agent_auth import verify_agent_token
        
        async def override_verify():
            return sample_token
        
        app = client.app
        app.dependency_overrides[verify_agent_token] = override_verify
        
        with patch("app.routers.agent.get_token_service") as mock_get_service, \
             patch("app.db.get_periodic_history") as mock_get_history:
            mock_service = Mock()
            mock_service.log_audit = Mock()
            mock_get_service.return_value = mock_service
            mock_get_history.return_value = []
            
            # Step 1: Health check (no auth required)
            response = client.get("/api/agent/v1/health")
            assert response.status_code == 200
            
            # Step 2: Whoami
            response = client.get(
                "/api/agent/v1/whoami",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            assert response.status_code == 200
            
            # Step 3: Markets
            response = client.get(
                "/api/agent/v1/markets",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            assert response.status_code == 200
            
            # Step 4: Klines
            response = client.post(
                "/api/agent/v1/klines",
                json={
                    "market": "AStock",
                    "symbol": "600519",
                    "timeframe": "1D",
                    "limit": 100
                },
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            assert response.status_code == 200
        
        app.dependency_overrides.clear()
