"""
Copilot Rate Limiting Tests

Tests for rate limiting on /api/v1/chat and /api/v1/copilot/* endpoints.
"""
import pytest
from unittest.mock import Mock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset the in-memory rate limiter before each test"""
    from app.middleware.rate_limit import get_limiter
    limiter = get_limiter()
    limiter.reset()
    yield
    limiter.reset()


class TestCopilotRateLimitConfig:
    """Tests for copilot rate limit configuration"""
    
    def test_copilot_limit_exists(self):
        """Should have copilot rate limit configured"""
        from app.config.rate_limit import ENDPOINT_LIMITS
        
        assert "copilot" in ENDPOINT_LIMITS
        
        copilot_limit = ENDPOINT_LIMITS["copilot"]
        assert copilot_limit.requests == 30
        assert copilot_limit.period == 60
    
    def test_copilot_limit_stricter_than_default(self):
        """Copilot limit should be stricter than default"""
        from app.config.rate_limit import ENDPOINT_LIMITS
        
        copilot_limit = ENDPOINT_LIMITS["copilot"]
        default_limit = ENDPOINT_LIMITS["default"]
        
        assert copilot_limit.requests < default_limit.requests


class TestCopilotPathCategorization:
    """Tests for copilot path categorization"""
    
    def test_chat_path_categorized_as_copilot(self):
        """Should categorize /api/v1/chat as copilot"""
        from app.config.rate_limit import get_endpoint_category
        
        assert get_endpoint_category("/api/v1/chat") == "copilot"
    
    def test_copilot_path_categorized_as_copilot(self):
        """Should categorize /api/v1/copilot/* as copilot"""
        from app.config.rate_limit import get_endpoint_category
        
        assert get_endpoint_category("/api/v1/copilot/status") == "copilot"
        assert get_endpoint_category("/api/v1/copilot/message") == "copilot"
        assert get_endpoint_category("/api/v1/copilot/stream") == "copilot"
    
    def test_other_paths_not_categorized_as_copilot(self):
        """Should not categorize other paths as copilot"""
        from app.config.rate_limit import get_endpoint_category
        
        assert get_endpoint_category("/api/v1/market/overview") != "copilot"
        assert get_endpoint_category("/api/v1/f9/600519/financial") != "copilot"
        assert get_endpoint_category("/api/v1/backtest/run") != "copilot"


class TestCopilotRateLimitMiddleware:
    """Tests for copilot rate limiting middleware integration"""
    
    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter before each test"""
        from app.middleware.rate_limit import get_limiter
        get_limiter().reset()
        yield
        get_limiter().reset()
    
    @pytest.fixture
    def app_with_copilot_rate_limit(self):
        """Create a FastAPI app with copilot endpoints and rate limiting"""
        from app.middleware.rate_limit import RateLimitMiddleware, RateLimitConfig
        
        app = FastAPI()
        
        @app.post("/api/v1/chat")
        async def chat_endpoint():
            return {"response": "AI response"}
        
        @app.get("/api/v1/copilot/status")
        async def copilot_status():
            return {"status": "ready"}
        
        @app.post("/api/v1/copilot/message")
        async def copilot_message():
            return {"message": "AI message"}
        
        config = RateLimitConfig(
            global_limit=200,
            global_period=60,
            enabled=True
        )
        app.add_middleware(RateLimitMiddleware, config=config)
        
        return app
    
    def test_copilot_allows_requests_within_limit(self, app_with_copilot_rate_limit):
        """Should allow copilot requests within limit (30 per 60s)"""
        client = TestClient(app_with_copilot_rate_limit)
        
        # Should allow 30 requests
        for i in range(30):
            response = client.post("/api/v1/chat", json={"message": "test"})
            assert response.status_code == 200
            assert "x-ratelimit-limit" in response.headers
            assert response.headers["x-ratelimit-limit"] == "30"
    
    def test_copilot_blocks_excess_requests(self, app_with_copilot_rate_limit):
        """Should block copilot requests exceeding 30 per 60s"""
        client = TestClient(app_with_copilot_rate_limit)
        
        for i in range(30):
            response = client.post("/api/v1/chat", json={"message": "test"})
            assert response.status_code == 200

        response = client.post("/api/v1/chat", json={"message": "test"})
        assert response.status_code == 429
        
        import json
        body = json.loads(response.content)
        assert body["code"] == 429
        assert "retry_after" in body
        assert "retry-after" in response.headers
    
    def test_copilot_rate_limit_headers(self, app_with_copilot_rate_limit):
        """Should include rate limit headers in copilot responses"""
        client = TestClient(app_with_copilot_rate_limit)
        
        response = client.post("/api/v1/chat", json={"message": "test"})
        
        assert "x-ratelimit-limit" in response.headers
        assert response.headers["x-ratelimit-limit"] == "30"
        
        assert "x-ratelimit-remaining" in response.headers
        remaining = int(response.headers["x-ratelimit-remaining"])
        assert 0 <= remaining <= 30
        
        assert "x-ratelimit-reset" in response.headers
    
    def test_copilot_different_endpoints_share_limit(self, app_with_copilot_rate_limit):
        """Different copilot endpoints should share the same rate limit"""
        client = TestClient(app_with_copilot_rate_limit)
        
        for i in range(15):
            response = client.post("/api/v1/chat", json={"message": "test"})
            assert response.status_code == 200

        for i in range(15):
            response = client.post("/api/v1/copilot/message", json={"message": "test"})
            assert response.status_code == 200

        response = client.post("/api/v1/copilot/status")
    
    def test_copilot_429_response_format(self, app_with_copilot_rate_limit):
        """429 response should have correct format for copilot"""
        client = TestClient(app_with_copilot_rate_limit)
        
        for i in range(30):
            client.post("/api/v1/chat", json={"message": "test"})

        response = client.post("/api/v1/chat", json={"message": "test"})
        
        assert response.status_code == 429
        assert "retry-after" in response.headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        
        body = response.json()
        assert body["code"] == 429
        assert "message" in body
        assert "retry_after" in body


class TestCopilotRateLimitIsolation:
    """Tests for rate limit isolation between copilot and other endpoints"""
    
    @pytest.fixture(autouse=True)
    def reset_rate_limiter(self):
        """Reset rate limiter before each test"""
        from app.middleware.rate_limit import get_limiter
        get_limiter().reset()
        yield
        get_limiter().reset()
    
    @pytest.fixture
    def app_with_mixed_endpoints(self):
        """Create a FastAPI app with copilot and other endpoints"""
        from app.middleware.rate_limit import RateLimitMiddleware, RateLimitConfig
        
        app = FastAPI()
        
        @app.post("/api/v1/chat")
        async def chat():
            return {"response": "AI response"}
        
        @app.get("/api/v1/market/overview")
        async def market():
            return {"market": "data"}
        
        config = RateLimitConfig(
            global_limit=200,
            global_period=60,
            enabled=True
        )
        app.add_middleware(RateLimitMiddleware, config=config)
        
        return app
    
    def test_copilot_limit_independent_from_market(self, app_with_mixed_endpoints):
        """Copilot rate limit should be independent from market rate limit"""
        client = TestClient(app_with_mixed_endpoints)
        
        for i in range(30):
            response = client.post("/api/v1/chat", json={"message": "test"})
            assert response.status_code == 200

        response = client.post("/api/v1/chat", json={"message": "test"})
        assert response.status_code == 429

        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
        assert response.headers["x-ratelimit-limit"] == "60"
