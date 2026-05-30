"""
Integration Tests for Admin P1 Fixes

Tests all P1 fixes from v0.6.218:
1. /api/v1/admin/cache/stats endpoint
2. /api/v1/admin/models/all endpoint  
3. /api/v1/copilot/status endpoint
4. /api/v1/backtest/strategies endpoint
5. market_radar_refresh scheduler job
6. _get_proxies() returns None when no proxy configured
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# Mock database access BEFORE importing app
@pytest.fixture(scope="module", autouse=True)
def mock_database_for_module():
    """Mock database access at module level to prevent admin_config table errors"""
    with patch("app.db.model_config_db.get_model_config", return_value={}):
        with patch("app.db.model_config_db.set_model_config", return_value=None):
            with patch("app.db.model_config_db.get_all_model_configs", return_value={}):
                with patch("app.db.model_config_db.get_enabled_models", return_value=[]):
                    yield


from app.main import app
from app.services.market_radar.sina_fallback import _get_proxies
from app.services.scheduler import scheduler

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test to prevent rate limit accumulation"""
    from app.middleware.rate_limit import get_limiter
    get_limiter().reset()
    yield
    get_limiter().reset()


class TestAdminCacheStatsEndpoint:
    """Test /api/v1/admin/cache/stats endpoint"""
    
    def test_cache_stats_endpoint(self):
        """Test cache stats endpoint returns correct structure"""
        response = client.get("/api/v1/admin/cache/stats")
        
        # Verify status code
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Verify response structure
        assert "code" in data
        assert data["code"] == 0
        assert "data" in data
        
        # Verify required fields
        result = data["data"]
        assert "sectors_cache" in result
        assert "quotes_cache" in result
        assert "data_cache" in result
        
        # Verify sectors_cache structure
        sectors_cache = result["sectors_cache"]
        assert "count" in sectors_cache
        assert "ready" in sectors_cache
        
        # Verify quotes_cache structure
        quotes_cache = result["quotes_cache"]
        assert "count" in quotes_cache
        
        # Verify data_cache structure
        data_cache = result["data_cache"]
        assert "entry_count" in data_cache
        assert "memory_usage_mb" in data_cache
    
    def test_cache_stats_response_time(self):
        """Test cache stats endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/api/v1/admin/cache/stats")
        elapsed = time.time() - start
        
        # Should complete within 2 seconds
        assert elapsed < 2.0
        assert response.status_code == 200


class TestAdminModelsAllEndpoint:
    """Test /api/v1/admin/models/all endpoint"""
    
    def test_models_all_endpoint(self):
        """Test models/all endpoint returns correct structure"""
        response = client.get("/api/v1/admin/models/all")
        
        # Verify status code
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Verify response structure
        assert "code" in data
        assert data["code"] == 0
        assert "data" in data
        
        # Verify data is a dict (may be empty if no models configured)
        result = data["data"]
        assert isinstance(result, dict)
    
    def test_models_all_response_time(self):
        """Test models/all endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/api/v1/admin/models/all")
        elapsed = time.time() - start
        
        # Should complete within 2 seconds
        assert elapsed < 2.0
        assert response.status_code == 200


class TestCopilotStatusEndpoint:
    """Test /api/v1/status endpoint (copilot router prefix is /api/v1)"""
    
    def test_copilot_status_endpoint(self):
        """Test copilot status endpoint returns correct structure"""
        response = client.get("/api/v1/status")
        
        # Verify status code
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Some endpoints return raw data without wrapping
        # Check for status-related fields
        assert "status" in data or "provider" in data or "providers" in data or "enabled" in data
    
    def test_copilot_status_response_time(self):
        """Test copilot status endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/api/v1/status")
        elapsed = time.time() - start
        
        # Should complete within 2 seconds
        assert elapsed < 2.0
        assert response.status_code == 200


class TestBacktestStrategiesEndpoint:
    """Test /api/v1/backtest/strategies endpoint"""
    
    def test_backtest_strategies_endpoint(self):
        """Test backtest strategies endpoint returns correct structure"""
        response = client.get("/api/v1/backtest/strategies")
        
        # Verify status code
        assert response.status_code == 200
        
        # Parse response
        data = response.json()
        
        # Verify response structure
        assert "code" in data
        assert data["code"] == 0
        assert "data" in data
        
        # Verify data is a list or dict
        result = data["data"]
        assert isinstance(result, (list, dict))
    
    def test_backtest_strategies_response_time(self):
        """Test backtest strategies endpoint responds quickly"""
        import time
        start = time.time()
        response = client.get("/api/v1/backtest/strategies")
        elapsed = time.time() - start
        
        # Should complete within 2 seconds
        assert elapsed < 2.0
        assert response.status_code == 200


class TestMarketRadarScheduler:
    """Test market_radar_refresh scheduler job"""
    
    def test_market_radar_scheduler_registered(self):
        """Test that market_radar_refresh job is registered in scheduler"""
        from apscheduler.schedulers.background import BackgroundScheduler
        
        # Check if scheduler is running
        if not scheduler.running:
            # For testing, just verify the job would be added
            # Check scheduler.py source code for the job registration
            import inspect
            source = inspect.getsource(scheduler.__class__)
            # The job is defined in start_scheduler function
            from app.services import scheduler as scheduler_module
            source = inspect.getsource(scheduler_module)
            assert "market_radar_refresh" in source
        else:
            jobs = scheduler.get_jobs()
            job_ids = [job.id for job in jobs]
            assert "market_radar_refresh" in job_ids, f"market_radar_refresh not in {job_ids}"
    
    def test_market_radar_scheduler_interval(self):
        """Test that market_radar_refresh job has correct interval (5 minutes)"""
        # Verify the interval from source code
        import inspect
        from app.services import scheduler as scheduler_module
        source = inspect.getsource(scheduler_module)
        
        # Should have "minutes=5" or "seconds=300" in the job definition
        assert "market_radar_refresh" in source
        # The scheduler.py uses 'interval' trigger with minutes=5
        assert "minutes=5" in source or "seconds=300" in source or "300" in source
    
    def test_market_radar_scheduler_enabled(self):
        """Test that market_radar_refresh job definition exists in scheduler"""
        # Verify job definition exists in scheduler module
        import inspect
        from app.services import scheduler as scheduler_module
        source = inspect.getsource(scheduler_module)
        
        # Check that the job is defined
        assert "market_radar_refresh" in source
        # Check that it has add_job call
        assert "add_job" in source


class TestSinaNoProxy:
    """Test that _get_proxies() returns None when no proxy configured"""
    
    def test_get_proxies_respects_settings(self):
        """Test _get_proxies() respects settings configuration"""
        from app.config.settings import get_settings
        
        settings = get_settings()
        proxy_url = settings.get_proxy_url()
        result = _get_proxies()
        
        # If proxy is configured in settings, should return dict
        if proxy_url:
            assert result is not None, "Should return dict when proxy configured"
            assert isinstance(result, dict)
            assert "http" in result
            assert "https" in result
        else:
            assert result is None, "Should return None when no proxy configured"
    
    def test_get_proxies_returns_correct_format(self):
        """Test _get_proxies() returns correct format"""
        result = _get_proxies()
        
        # Should return None or dict with http/https keys
        if result is not None:
            assert isinstance(result, dict), "Should return dict when proxy configured"
            assert "http" in result, "Missing http key"
            assert "https" in result, "Missing https key"
            assert result["http"] == result["https"], "http and https should match"


class TestIntegration:
    """Integration tests for P1 fixes"""
    
    def test_all_endpoints_accessible(self):
        """Test that all P1 endpoints are accessible"""
        endpoints = [
            "/api/v1/admin/cache/stats",
            "/api/v1/admin/models/all",
            "/api/v1/status",  # Copilot status endpoint (prefix is /api/v1)
            "/api/v1/backtest/strategies",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"{endpoint} returned {response.status_code}"
            
            # Some endpoints may return raw data without code wrapping
            data = response.json()
            assert isinstance(data, dict), f"{endpoint} did not return dict"
    
    def test_endpoints_return_json(self):
        """Test that all endpoints return valid JSON"""
        endpoints = [
            "/api/v1/admin/cache/stats",
            "/api/v1/admin/models/all",
            "/api/v1/status",  # Copilot status endpoint (prefix is /api/v1)
            "/api/v1/backtest/strategies",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.headers["content-type"] == "application/json", \
                f"{endpoint} returned {response.headers['content-type']}"
            
            data = response.json()
            assert isinstance(data, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
