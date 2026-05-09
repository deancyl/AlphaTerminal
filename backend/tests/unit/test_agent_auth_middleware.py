"""
Unit tests for Agent Authentication Middleware.

Tests:
- Token verification
- Scope enforcement
- Rate limiting
- Audit logging
- Request context injection

Author: AlphaTerminal Team
Version: 0.6.12
"""

import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Depends
from fastapi.testclient import TestClient
from fastapi import HTTPException, status

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.middleware.agent_auth import (
    verify_agent_token,
    require_scope,
    audit_middleware,
    get_current_token,
    RequestContext,
)
from app.services.agent.token_service import AgentToken, TokenScope, AgentTokenService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_token_service():
    """Mock token service."""
    with patch('app.middleware.agent_auth.get_token_service') as mock:
        service = MagicMock()
        mock.return_value = service
        yield service


@pytest.fixture
def sample_token():
    """Create a sample token for testing."""
    return AgentToken(
        id="test-token-id",
        name="Test Token",
        token_prefix="AGT1_test123",
        token_hash="test_hash_123",
        scopes=[TokenScope.READ, TokenScope.WRITE],
        markets=["*"],
        instruments=["*"],
        paper_only=True,
        rate_limit=120,
        created_at=datetime.now(),
        is_active=True,
        access_count=0,
    )


@pytest.fixture
def expired_token():
    """Create an expired token for testing."""
    return AgentToken(
        id="expired-token-id",
        name="Expired Token",
        token_prefix="AGT1_expired",
        token_hash="expired_hash",
        scopes=[TokenScope.READ],
        markets=["*"],
        instruments=["*"],
        paper_only=True,
        rate_limit=120,
        expires_at=datetime.now() - timedelta(hours=1),
        created_at=datetime.now() - timedelta(days=1),
        is_active=True,
        access_count=0,
    )


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    audit_middleware(app)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ============================================================================
# Token Verification Tests
# ============================================================================

class TestVerifyAgentToken:
    """Test verify_agent_token dependency."""
    
    @pytest.mark.asyncio
    async def test_verify_token_success(self, mock_token_service, sample_token):
        """Test successful token verification."""
        # Setup
        mock_token_service.verify_token.return_value = sample_token
        mock_token_service.check_rate_limit.return_value = True
        
        # Create mock request
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint(token = None):
            from fastapi import Request
            from app.middleware.agent_auth import verify_agent_token
            from fastapi.security import HTTPAuthorizationCredentials
            
            # Create mock request
            request = MagicMock()
            request.url.path = "/test"
            request.method = "GET"
            request.client.host = "127.0.0.1"
            request.headers = {"user-agent": "test-agent"}
            request.state = MagicMock()
            
            # Create mock credentials
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="AGT1_test_token"
            )
            
            # Verify token
            result = await verify_agent_token(request, credentials)
            return {"token_id": result.id}
        
        client = TestClient(app)
        
        # Mock the token service
        with patch('app.middleware.agent_auth.get_token_service') as mock_service:
            service = MagicMock()
            service.verify_token.return_value = sample_token
            service.check_rate_limit.return_value = True
            mock_service.return_value = service
            
            # Test
            response = client.get(
                "/test",
                headers={"Authorization": "Bearer AGT1_test_token"}
            )
            
            # Verify
            assert response.status_code == 200
            assert response.json()["token_id"] == "test-token-id"
    
    @pytest.mark.asyncio
    async def test_verify_token_missing_header(self):
        """Test token verification with missing header."""
        from fastapi import Request
        from app.middleware.agent_auth import verify_agent_token
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.state = MagicMock()
        
        # Verify token should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await verify_agent_token(request, None)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing Authorization header" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_verify_token_invalid_token(self, mock_token_service):
        """Test token verification with invalid token."""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials
        from app.middleware.agent_auth import verify_agent_token
        
        # Setup
        mock_token_service.verify_token.return_value = None
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.state = MagicMock()
        
        # Create mock credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid_token"
        )
        
        # Verify token should raise exception
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_agent_token(request, credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or expired token" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_verify_token_expired(self, mock_token_service, expired_token):
        """Test token verification with expired token."""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials
        from app.middleware.agent_auth import verify_agent_token
        
        # Setup
        mock_token_service.verify_token.return_value = expired_token
        mock_token_service.check_rate_limit.return_value = True
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.state = MagicMock()
        
        # Create mock credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="expired_token"
        )
        
        # Verify token should raise exception
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_agent_token(request, credentials)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Token expired" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_verify_token_rate_limited(self, mock_token_service, sample_token):
        """Test token verification with rate limit exceeded."""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials
        from app.middleware.agent_auth import verify_agent_token
        
        # Setup
        mock_token_service.verify_token.return_value = sample_token
        mock_token_service.check_rate_limit.return_value = False
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.client.host = "127.0.0.1"
        request.headers = {"user-agent": "test-agent"}
        request.state = MagicMock()
        
        # Create mock credentials
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="rate_limited_token"
        )
        
        # Verify token should raise exception
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_agent_token(request, credentials)
            
            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Rate limit exceeded" in exc_info.value.detail


# ============================================================================
# Scope Enforcement Tests
# ============================================================================

class TestRequireScope:
    """Test require_scope dependency factory."""
    
    @pytest.mark.asyncio
    async def test_require_scope_success(self, mock_token_service, sample_token):
        """Test successful scope check."""
        from fastapi import Request
        from app.middleware.agent_auth import require_scope
        
        # Setup
        mock_token_service.check_scope.return_value = True
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.state = MagicMock()
        request.state.auth_context = RequestContext(
            token=sample_token,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        
        # Create scope checker
        scope_checker = require_scope(TokenScope.READ)
        
        # Test
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            result = await scope_checker(request, sample_token)
            
            assert result == sample_token
    
    @pytest.mark.asyncio
    async def test_require_scope_insufficient(self, mock_token_service, sample_token):
        """Test scope check with insufficient scope."""
        from fastapi import Request
        from app.middleware.agent_auth import require_scope
        
        # Setup - token only has READ and WRITE, not BACKTEST
        mock_token_service.check_scope.return_value = False
        
        # Create mock request
        request = MagicMock()
        request.url.path = "/test"
        request.method = "GET"
        request.state = MagicMock()
        request.state.auth_context = RequestContext(
            token=sample_token,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        
        # Create scope checker for BACKTEST
        scope_checker = require_scope(TokenScope.BACKTEST)
        
        # Test
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            with pytest.raises(HTTPException) as exc_info:
                await scope_checker(request, sample_token)
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Insufficient scope" in exc_info.value.detail


# ============================================================================
# Request Context Tests
# ============================================================================

class TestRequestContext:
    """Test request context injection."""
    
    def test_context_creation(self, sample_token):
        """Test creating request context."""
        context = RequestContext(
            token=sample_token,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        
        assert context.token == sample_token
        assert context.ip_address == "127.0.0.1"
        assert context.user_agent == "test-agent"
        assert context.request_start_time > 0
    
    def test_context_to_dict(self, sample_token):
        """Test converting context to dictionary."""
        context = RequestContext(
            token=sample_token,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        
        result = context.to_dict()
        
        assert result["token_id"] == sample_token.id
        assert result["token_name"] == sample_token.name
        assert result["ip_address"] == "127.0.0.1"
        assert result["user_agent"] == "test-agent"
        assert "request_duration" in result
    
    def test_get_current_token(self, sample_token):
        """Test getting current token from request."""
        request = MagicMock()
        request.state = MagicMock()
        request.state.auth_context = RequestContext(
            token=sample_token,
            ip_address="127.0.0.1",
            user_agent="test-agent"
        )
        
        token = get_current_token(request)
        
        assert token == sample_token
    
    def test_get_current_token_none(self):
        """Test getting current token when none exists."""
        request = MagicMock()
        request.state = MagicMock()
        request.state.auth_context = RequestContext()
        
        token = get_current_token(request)
        
        assert token is None


# ============================================================================
# Audit Middleware Tests
# ============================================================================

class TestAuditMiddleware:
    """Test audit middleware."""
    
    def test_audit_middleware_agent_api(self, app, mock_token_service, sample_token):
        """Test audit middleware for agent API requests."""
        # Setup
        mock_token_service.verify_token.return_value = sample_token
        mock_token_service.check_rate_limit.return_value = True
        
        @app.get("/api/agent/v1/test")
        async def test_endpoint(token = None):
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Test
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            response = client.get(
                "/api/agent/v1/test",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
    
    def test_audit_middleware_non_agent_api(self, app):
        """Test audit middleware for non-agent API requests."""
        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Test
        response = client.get("/api/v1/test")
        
        assert response.status_code == 200
    
    def test_audit_middleware_http_exception(self, app, mock_token_service, sample_token):
        """Test audit middleware handling HTTP exceptions."""
        # Setup
        mock_token_service.verify_token.return_value = sample_token
        mock_token_service.check_rate_limit.return_value = True
        
        from fastapi import HTTPException
        
        @app.get("/api/agent/v1/error")
        async def error_endpoint():
            raise HTTPException(status_code=400, detail="Test error")
        
        client = TestClient(app)
        
        # Test
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            response = client.get(
                "/api/agent/v1/error",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 400


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the complete authentication flow."""
    
    def test_complete_auth_flow(self, app, mock_token_service, sample_token):
        """Test complete authentication flow."""
        # Setup
        mock_token_service.verify_token.return_value = sample_token
        mock_token_service.check_rate_limit.return_value = True
        mock_token_service.check_scope.return_value = True
        
        @app.get("/api/agent/v1/protected")
        async def protected_endpoint(token = None):
            return {"token_id": "test"}
        
        client = TestClient(app)
        
        # Test
        with patch('app.middleware.agent_auth.get_token_service') as mock:
            mock.return_value = mock_token_service
            
            response = client.get(
                "/api/agent/v1/protected",
                headers={"Authorization": "Bearer test_token"}
            )
            
            assert response.status_code == 200
    
    def test_auth_without_token(self, app):
        """Test authentication without token."""
        from app.middleware.agent_auth import verify_agent_token
        
        @app.get("/api/agent/v1/protected")
        async def protected_endpoint(token = Depends(verify_agent_token)):
            return {"token_id": token.id}
        
        client = TestClient(app)
        
        # Test without token
        response = client.get("/api/agent/v1/protected")
        
        # Should return 401
        assert response.status_code == 401


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])