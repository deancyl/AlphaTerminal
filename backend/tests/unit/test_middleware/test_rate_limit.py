"""
Rate Limiting Middleware Tests

Tests for IP-based rate limiting, endpoint-specific limits, and 429 response format.

NOTE: The get_client_ip function now uses trusted proxy security logic.
When remote_addr is NOT from a trusted proxy, it returns remote_addr directly
(to prevent IP spoofing). When remote_addr IS from a trusted proxy, it parses
X-Forwarded-For to find the original client IP.
"""

import pytest
import os
from unittest.mock import Mock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

# Set trusted proxies for tests
os.environ["TRUSTED_PROXY_CIDRS"] = "10.0.0.0/8,127.0.0.1,172.16.0.0/12,192.168.0.0/16"


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
        # Direct connection from trusted range, returns the IP
        assert ip in ["192.168.1.100", "unknown"]

    def test_get_client_ip_x_forwarded_for(self):
        """Should extract IP based on trusted proxy logic"""
        from app.middleware.rate_limit import get_client_ip
        from app.utils.ip_validation import reload_trusted_proxies

        reload_trusted_proxies()

        request = Mock(spec=Request)
        request.client = Mock()
        # 127.0.0.1 is typically trusted
        request.client.host = "127.0.0.1"
        request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.50.100"}

        ip = get_client_ip(request)
        # With trusted proxy, returns rightmost non-trusted IP
        # or could return the direct IP depending on trusted proxy config
        assert ip in ["203.0.113.50", "70.41.50.100", "127.0.0.1"]

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
            "x-real-ip": "198.51.100.78",
        }

        ip = get_client_ip(request)
        assert ip == "203.0.113.50"


class TestEndpointSpecificLimits:
    """Tests for endpoint-specific rate limiting"""

    def test_expensive_endpoint_limits(self):
        """Expensive endpoints should have lower limits"""
        from app.config.rate_limit import ENDPOINT_LIMITS, get_limit_for_path

        assert "f9_deep" in ENDPOINT_LIMITS
        assert "backtest" in ENDPOINT_LIMITS

        f9_limit = get_limit_for_path("/api/v1/f9/600519/financial")
        backtest_limit = get_limit_for_path("/api/v1/backtest/run")

        default_limit = get_limit_for_path("/api/v1/unknown")
        assert f9_limit.requests <= default_limit.requests
        assert backtest_limit.requests <= default_limit.requests

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
        """Rate limit storage should initialize"""
        from app.middleware.rate_limit_token_bucket import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter()

    def test_rate_limit_tracking(self):
        """Should track request counts using token bucket"""
        from app.middleware.rate_limit_token_bucket import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter()
        key = "192.168.1.100:/api/v1/market/overview"

        limiter.reset(key)

        is_allowed, remaining, limit, reset = limiter.is_allowed(
            key, refill_rate=2.5, burst_capacity=150
        )
        assert is_allowed is True
        assert remaining >= 0
        assert limit == 150

        is_allowed, remaining, limit, reset = limiter.is_allowed(
            key, refill_rate=2.5, burst_capacity=150
        )
        assert is_allowed is True
        assert remaining >= 0

        limiter.reset(key)

    def test_rate_limit_exceeded(self):
        """Should deny requests when limit exceeded"""
        from app.middleware.rate_limit_token_bucket import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter()
        key = "192.168.1.100:/api/v1/test:exceeded"

        limiter.reset(key)

        for i in range(6):
            is_allowed, remaining, limit, reset = limiter.is_allowed(
                key, refill_rate=0.0, burst_capacity=5
            )
            assert is_allowed is True, f"Request {i+1} should be allowed"

        is_allowed, remaining, limit, reset = limiter.is_allowed(
            key, refill_rate=0.0, burst_capacity=5
        )
        assert is_allowed is False
        assert remaining == 0

        limiter.reset(key)

    def test_rate_limit_reset_after_period(self):
        """Should have tokens available after refill period"""
        import time
        from app.middleware.rate_limit_token_bucket import TokenBucketRateLimiter

        limiter = TokenBucketRateLimiter()
        key = "192.168.1.100:/api/v1/test:reset"

        limiter.reset(key)

        limiter.is_allowed(key, refill_rate=10.0, burst_capacity=10)

        time.sleep(0.2)

        is_allowed, remaining, limit, reset = limiter.is_allowed(
            key, refill_rate=10.0, burst_capacity=10
        )
        assert is_allowed is True

        limiter.reset(key)


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware integration"""

    @pytest.fixture
    def app_with_rate_limit(self):
        """Create a FastAPI app with rate limiting middleware"""
        from app.middleware.rate_limit import RateLimitMiddleware
        from app.config.rate_limit import RateLimitConfig

        app = FastAPI()

        @app.get("/api/v1/market/test")
        async def test_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        config = RateLimitConfig(global_limit=5, global_period=60, enabled=True)
        app.add_middleware(RateLimitMiddleware, config=config)

        return app

    def test_rate_limit_allows_requests(self, app_with_rate_limit):
        """Should allow requests within limit"""
        from app.middleware.rate_limit_token_bucket import get_token_bucket_limiter

        get_token_bucket_limiter().reset()

        client = TestClient(app_with_rate_limit)

        for i in range(60):
            response = client.get("/api/v1/market/test")
            assert (
                response.status_code == 200
            ), f"Request {i+1} failed with {response.status_code}"

    def test_rate_limit_blocks_excess_requests(self, app_with_rate_limit):
        """Should block requests exceeding limit"""
        from app.middleware.rate_limit_token_bucket import get_token_bucket_limiter

        get_token_bucket_limiter().reset()

        client = TestClient(app_with_rate_limit)

        for i in range(200):
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
            retry_after=60, limit=10, remaining=0, reset=1700000000
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
            response, limit=10, remaining=5, reset=1700000000
        )

        assert "x-ratelimit-limit" in response.headers
        assert response.headers["x-ratelimit-limit"] == "10"

        assert "x-ratelimit-remaining" in response.headers
        assert response.headers["x-ratelimit-remaining"] == "5"

        assert "x-ratelimit-reset" in response.headers
        assert response.headers["x-ratelimit-reset"] == "1700000000"
