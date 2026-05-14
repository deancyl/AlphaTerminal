"""
Rate Limiting Middleware Tests

Tests for IP-based rate limiting, endpoint-specific limits, and 429 response format.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse


class TestIPBasedRateLimiting:
    """Tests for IP-based rate limiting logic"""
    
    def test_get_client_ip_direct(self):
        """Should extract IP from direct connection"""
        from app.middleware.rate_limit import get_client_ip
        
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.headers = {}
        
        ip = get_client_ip(request)
        assert ip == "192.168.1.100"
    
    def test_get_client_ip_x_forwarded_for(self):
        """Should extract IP from X-Forwarded-For header (first IP)"""
        from app.middleware.rate_limit import get_client_ip
        
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.50.100"}
        
        ip = get_client_ip(request)
        assert ip == "203.0.113.50"
    
    def test_get_client_ip_x_real_ip(self):
        """Should extract IP from X-Real-IP header"""
        from app.middleware.rate_limit import get_client_ip
        
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {"x-real-ip": "198.51.100.78"}
        
        ip = get_client_ip(request)
        assert ip == "198.51.100.78"
    
    def test_get_client_ip_forwarded_priority(self):
        """X-Forwarded-For should take priority over X-Real-IP"""
        from app.middleware.rate_limit import get_client_ip
        
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.headers = {
            "x-forwarded-for": "203.0.113.50",
            "x-real-ip": "198.51.100.78"
        }
        
        ip = get_client_ip(request)
        assert ip == "203.0.113.50"


class TestEndpointSpecificLimits:
    """Tests for endpoint-specific rate limit configurations"""
    
    def test_global_limit_config(self):
        """Should have default global limit configured"""
        from app.middleware.rate_limit import RateLimitConfig
        
        config = RateLimitConfig()
        assert config.global_limit > 0
        assert config.global_period > 0
    
    def test_expensive_endpoint_limits(self):
        """Should have stricter limits for expensive endpoints"""
        from app.middleware.rate_limit import RateLimitConfig, ENDPOINT_LIMITS
        
        config = RateLimitConfig()
        
        assert "f9_deep" in ENDPOINT_LIMITS
        assert "backtest" in ENDPOINT_LIMITS
        
        f9_limit = ENDPOINT_LIMITS["f9_deep"]
        backtest_limit = ENDPOINT_LIMITS["backtest"]
        
        assert f9_limit.requests < config.global_limit
        assert backtest_limit.requests < config.global_limit
    
    def test_health_check_exempt(self):
        """Health check endpoints should be exempt from rate limiting"""
        from app.middleware.rate_limit import is_exempt_path
        
        assert is_exempt_path("/health")
        assert is_exempt_path("/api/v1/health")
        assert is_exempt_path("/api/v1/f9/health")
        
        assert not is_exempt_path("/api/v1/market/overview")
        assert not is_exempt_path("/api/v1/f9/600519/financial")


class TestRateLimitStorage:
    """Tests for rate limit storage and tracking"""
    
    def test_storage_initialization(self):
        """Rate limit storage should initialize empty"""
        from app.middleware.rate_limit import InMemoryRateLimiter
        
        limiter = InMemoryRateLimiter()
        assert len(limiter._storage) == 0
    
    def test_rate_limit_tracking(self):
        """Should track request counts per IP"""
        from app.middleware.rate_limit import InMemoryRateLimiter
        
        limiter = InMemoryRateLimiter()
        key = "192.168.1.100:/api/v1/market/overview"
        
        is_allowed, remaining, limit, reset = limiter.is_allowed(key, limit=10, period=60)
        assert is_allowed is True
        assert remaining == 9
        
        is_allowed, remaining, limit, reset = limiter.is_allowed(key, limit=10, period=60)
        assert is_allowed is True
        assert remaining == 8
    
    def test_rate_limit_exceeded(self):
        """Should deny requests when limit exceeded"""
        from app.middleware.rate_limit import InMemoryRateLimiter
        
        limiter = InMemoryRateLimiter()
        key = "192.168.1.100:/api/v1/test"
        
        for i in range(10):
            is_allowed, remaining, limit, reset = limiter.is_allowed(key, limit=10, period=60)
            assert is_allowed is True
        
        is_allowed, remaining, limit, reset = limiter.is_allowed(key, limit=10, period=60)
        assert is_allowed is False
        assert remaining == 0
    
    def test_rate_limit_reset_after_period(self):
        """Should reset count after period expires"""
        import time
        from app.middleware.rate_limit import InMemoryRateLimiter
        
        limiter = InMemoryRateLimiter()
        key = "192.168.1.100:/api/v1/test"
        
        limiter.is_allowed(key, limit=10, period=1)
        
        time.sleep(1.1)
        
        is_allowed, remaining, limit, reset = limiter.is_allowed(key, limit=10, period=1)
        assert is_allowed is True
        assert remaining == 9


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware integration"""
    
    @pytest.fixture
    def app_with_rate_limit(self):
        """Create a FastAPI app with rate limiting middleware"""
        from app.middleware.rate_limit import RateLimitMiddleware, RateLimitConfig
        
        app = FastAPI()
        
        @app.get("/api/v1/market/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        config = RateLimitConfig(
            global_limit=5,
            global_period=60,
            enabled=True
        )
        app.add_middleware(RateLimitMiddleware, config=config)
        
        return app
    
    def test_rate_limit_allows_requests(self, app_with_rate_limit):
        """Should allow requests within limit"""
        client = TestClient(app_with_rate_limit)
        
        for i in range(60):
            response = client.get("/api/v1/market/test")
            assert response.status_code == 200
    
    def test_rate_limit_blocks_excess_requests(self, app_with_rate_limit):
        """Should block requests exceeding limit"""
        client = TestClient(app_with_rate_limit)
        
        for i in range(61):
            response = client.get("/api/v1/market/test")
        
        assert response.status_code == 429
    
    def test_health_check_exempt(self, app_with_rate_limit):
        """Health check should bypass rate limiting"""
        client = TestClient(app_with_rate_limit)
        
        for i in range(10):
            response = client.get("/health")
            assert response.status_code == 200


class TestRateLimitResponseFormat:
    """Tests for 429 response format"""
    
    def test_429_response_structure(self):
        """429 response should have correct structure"""
        from app.middleware.rate_limit import create_rate_limit_response
        
        response = create_rate_limit_response(retry_after=60)
        
        assert response.status_code == 429
        
        import json
        body = json.loads(response.body)
        
        assert "code" in body
        assert body["code"] == 429
        assert "message" in body
        assert "retry_after" in body
    
    def test_429_retry_after_header(self):
        """429 response should include Retry-After header"""
        from app.middleware.rate_limit import create_rate_limit_response
        
        response = create_rate_limit_response(retry_after=60)
        
        assert "retry-after" in response.headers
        assert response.headers["retry-after"] == "60"
    
    def test_429_rate_limit_headers(self):
        """429 response should include rate limit info headers"""
        from app.middleware.rate_limit import create_rate_limit_response
        
        response = create_rate_limit_response(
            retry_after=60,
            limit=10,
            remaining=0,
            reset=1700000000
        )
        
        assert "x-ratelimit-limit" in response.headers
        assert response.headers["x-ratelimit-limit"] == "10"
        
        assert "x-ratelimit-remaining" in response.headers
        assert response.headers["x-ratelimit-remaining"] == "0"
        
        assert "x-ratelimit-reset" in response.headers
        assert response.headers["x-ratelimit-reset"] == "1700000000"


class TestRateLimitHeaders:
    """Tests for rate limit headers in normal responses"""
    
    def test_rate_limit_headers_added(self):
        """Should add rate limit headers to successful responses"""
        from app.middleware.rate_limit import add_rate_limit_headers
        
        response = JSONResponse(content={"status": "ok"})
        
        response = add_rate_limit_headers(
            response,
            limit=10,
            remaining=5,
            reset=1700000000
        )
        
        assert "x-ratelimit-limit" in response.headers
        assert response.headers["x-ratelimit-limit"] == "10"
        
        assert "x-ratelimit-remaining" in response.headers
        assert response.headers["x-ratelimit-remaining"] == "5"
        
        assert "x-ratelimit-reset" in response.headers
        assert response.headers["x-ratelimit-reset"] == "1700000000"
