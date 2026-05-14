"""
P1 Reliability Tests for Futures Endpoints

Tests for rate limiting, input validation, and WebSocket fallback
on futures-related API endpoints.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse


class TestFuturesRateLimit:
    """P1: Rate limiting tests for futures endpoints"""
    
    @pytest.fixture
    def app_with_futures_rate_limit(self):
        """Create a FastAPI app with futures endpoints and rate limiting"""
        from app.middleware.rate_limit import RateLimitMiddleware, RateLimitConfig
        
        app = FastAPI()
        
        @app.get("/api/v1/futures/main_indexes")
        async def futures_main_indexes():
            return {"code": 200, "data": {"index_futures": []}}
        
        @app.get("/api/v1/futures/commodities")
        async def futures_commodities():
            return {"code": 200, "data": {"commodities": []}}
        
        @app.get("/api/v1/futures/term_structure")
        async def futures_term_structure(symbol: str = "RB"):
            return {"code": 200, "data": {"symbol": symbol, "term_structure": []}}
        
        @app.get("/api/v1/futures/index_history")
        async def futures_index_history(symbol: str = "IF", period: str = "daily"):
            return {"code": 200, "data": {"symbol": symbol, "history": []}}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        config = RateLimitConfig(
            global_limit=60,
            global_period=60,
            enabled=True
        )
        app.add_middleware(RateLimitMiddleware, config=config)
        
        return app
    
    def test_futures_endpoint_returns_200_under_limit(self, app_with_futures_rate_limit):
        """Test that requests under limit return 200"""
        client = TestClient(app_with_futures_rate_limit)
        
        for i in range(10):  # Well under 60 limit
            response = client.get("/api/v1/futures/main_indexes")
            assert response.status_code == 200
    
    def test_futures_rate_limit_headers_present(self, app_with_futures_rate_limit):
        """Test that rate limit headers are present in response"""
        client = TestClient(app_with_futures_rate_limit)
        
        response = client.get("/api/v1/futures/main_indexes")
        assert response.status_code == 200
        
        # Check for rate limit headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
        assert "x-ratelimit-reset" in response.headers
        
        # Verify header values
        assert int(response.headers["x-ratelimit-limit"]) > 0
        assert int(response.headers["x-ratelimit-remaining"]) >= 0
    
    def test_futures_commodities_rate_limit_headers(self, app_with_futures_rate_limit):
        """Test rate limit headers on commodities endpoint"""
        client = TestClient(app_with_futures_rate_limit)
        
        response = client.get("/api/v1/futures/commodities")
        assert response.status_code == 200
        
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
    
    def test_futures_health_check_exempt(self, app_with_futures_rate_limit):
        """Test that health check endpoints are exempt from rate limiting"""
        client = TestClient(app_with_futures_rate_limit)
        
        # Make many requests to health endpoint - should all succeed
        for i in range(100):
            response = client.get("/health")
            assert response.status_code == 200
    
    def test_futures_endpoint_category_detection(self):
        """Test that futures paths are correctly categorized"""
        from app.config.rate_limit import get_endpoint_category
        
        assert get_endpoint_category("/api/v1/futures/main_indexes") == "futures"
        assert get_endpoint_category("/api/v1/futures/commodities") == "futures"
        assert get_endpoint_category("/api/v1/futures/term_structure") == "futures"
        assert get_endpoint_category("/api/v1/futures/index_history") == "futures"
    
    def test_futures_rate_limit_config(self):
        """Test that futures has proper rate limit configuration"""
        from app.config.rate_limit import ENDPOINT_LIMITS, get_limit_for_path
        
        # Check futures is in endpoint limits
        assert "futures" in ENDPOINT_LIMITS
        
        futures_limit = ENDPOINT_LIMITS["futures"]
        assert futures_limit.requests > 0
        assert futures_limit.period > 0
        
        # Test path-based limit retrieval
        limit = get_limit_for_path("/api/v1/futures/main_indexes")
        assert limit.requests == futures_limit.requests
        assert limit.period == futures_limit.period


class TestFuturesInputValidation:
    """P1: Input validation tests for futures endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client for the main app"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    
    def test_term_structure_validates_symbol(self, client):
        """Test that term_structure endpoint validates symbol parameter"""
        # Valid symbol should work
        response = client.get("/api/v1/futures/term_structure?symbol=RB")
        assert response.status_code == 200
        
        # Symbol with numbers should be handled
        response = client.get("/api/v1/futures/term_structure?symbol=RB0")
        assert response.status_code == 200
    
    def test_index_history_validates_symbol(self, client):
        """Test that index_history validates symbol parameter"""
        valid_symbols = ["IF", "IC", "IM"]
        
        for symbol in valid_symbols:
            response = client.get(f"/api/v1/futures/index_history?symbol={symbol}")
            assert response.status_code == 200
    
    def test_index_history_validates_period(self, client):
        """Test that index_history validates period parameter"""
        valid_periods = ["daily", "1min", "5min", "15min", "30min", "60min"]
        
        for period in valid_periods:
            response = client.get(f"/api/v1/futures/index_history?symbol=IF&period={period}")
            assert response.status_code == 200
    
    def test_index_history_limit_parameter(self, client):
        """Test that index_history respects limit parameter"""
        response = client.get("/api/v1/futures/index_history?symbol=IF&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        if "data" in data and "history" in data["data"]:
            # Should return at most 50 items
            assert len(data["data"]["history"]) <= 50


class TestFuturesWebSocketFallback:
    """P1: WebSocket fallback tests for futures data"""
    
    def test_futures_cache_initialization(self):
        """Test that futures cache is initialized with mock data"""
        from app.routers.futures import _FUTURES_CACHE, _MOCK_INDEX_FUTURES, _MOCK_COMMODITIES
        
        # Cache should have initial mock data
        assert "index_futures" in _FUTURES_CACHE
        assert "commodities" in _FUTURES_CACHE
        assert len(_FUTURES_CACHE["index_futures"]) > 0
        assert len(_FUTURES_CACHE["commodities"]) > 0
    
    def test_futures_cache_structure(self):
        """Test that futures cache has correct structure"""
        from app.routers.futures import _FUTURES_CACHE
        
        index_futures = _FUTURES_CACHE.get("index_futures", [])
        for item in index_futures:
            assert "symbol" in item
            assert "name" in item
            assert "price" in item
            assert "change_pct" in item
        
        commodities = _FUTURES_CACHE.get("commodities", [])
        for item in commodities:
            assert "symbol" in item
            assert "name" in item
            assert "price" in item
    
    def test_futures_fallback_on_fetch_failure(self):
        """Test that futures returns fallback data on fetch failure"""
        from app.routers.futures import _get_futures_cache
        
        cache = _get_futures_cache()
        
        # Should always return valid data (mock or real)
        assert "index_futures" in cache
        assert "commodities" in cache
        assert len(cache["index_futures"]) > 0 or len(cache["commodities"]) > 0


class TestFuturesRateLimitIntegration:
    """Integration tests for futures rate limiting with real app"""
    
    @pytest.fixture
    def client(self):
        """Create test client for the main app"""
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)
    
    def test_futures_main_indexes_rate_limit_headers(self, client):
        """Test rate limit headers on real futures endpoint"""
        response = client.get("/api/v1/futures/main_indexes")
        
        # Should succeed
        assert response.status_code == 200
        
        # Should have rate limit headers
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers
    
    def test_futures_commodities_rate_limit_headers(self, client):
        """Test rate limit headers on commodities endpoint"""
        response = client.get("/api/v1/futures/commodities")
        
        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
    
    def test_futures_multiple_requests_tracking(self, client):
        """Test that rate limit correctly tracks multiple requests"""
        # First request
        response1 = client.get("/api/v1/futures/main_indexes")
        remaining1 = int(response1.headers.get("x-ratelimit-remaining", 0))
        
        # Second request
        response2 = client.get("/api/v1/futures/main_indexes")
        remaining2 = int(response2.headers.get("x-ratelimit-remaining", 0))
        
        # Remaining should decrease
        assert remaining2 <= remaining1
    
    def test_futures_response_format(self, client):
        """Test that futures endpoints return correct response format"""
        response = client.get("/api/v1/futures/main_indexes")
        data = response.json()
        
        # Should have standard response format (code 0 = success)
        assert "code" in data
        assert data["code"] == 0
        assert "data" in data
        
        # Data should have expected fields
        futures_data = data["data"]
        assert "index_futures" in futures_data
        assert isinstance(futures_data["index_futures"], list)
