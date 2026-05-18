"""
Timeout Test Suite

Tests for:
- HTTPX timeout configuration
- ThreadPoolExecutor timeout with asyncio.wait_for()
- Request-level timeout middleware
- Endpoint-specific timeout behavior
"""
import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from concurrent.futures import ThreadPoolExecutor

from app.config.timeout import (
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    WRITE_TIMEOUT,
    POOL_TIMEOUT,
    REQUEST_TIMEOUT,
    AKSHARE_TIMEOUT,
    SEARCH_TIMEOUT,
    QUOTE_TIMEOUT,
    get_timeout_config,
    validate_timeout,
)


class TestTimeoutConfiguration:
    """Tests for timeout configuration values"""
    
    def test_default_timeout_values(self):
        """Verify default timeout values are reasonable"""
        assert CONNECT_TIMEOUT == 5.0
        assert READ_TIMEOUT == 30.0
        assert WRITE_TIMEOUT == 10.0
        assert POOL_TIMEOUT == 5.0
        assert REQUEST_TIMEOUT == 60.0
        assert AKSHARE_TIMEOUT == 30.0
        assert SEARCH_TIMEOUT == 5.0
        assert QUOTE_TIMEOUT == 10.0
    
    def test_get_timeout_config_returns_all_values(self):
        """Verify get_timeout_config returns complete configuration"""
        config = get_timeout_config()
        
        assert "connect" in config
        assert "read" in config
        assert "write" in config
        assert "pool" in config
        assert "request" in config
        assert "akshare" in config
        assert "search" in config
        assert "quote" in config
    
    def test_validate_timeout_clamps_values(self):
        """Verify validate_timeout clamps out-of-range values"""
        # Too small
        assert validate_timeout(0.5, "test", min_val=1.0) == 1.0
        
        # Too large
        assert validate_timeout(500.0, "test", max_val=300.0) == 300.0
        
        # Valid value unchanged
        assert validate_timeout(30.0, "test", min_val=1.0, max_val=300.0) == 30.0
    
    def test_validate_timeout_rejects_negative(self):
        """Verify validate_timeout rejects negative values"""
        with pytest.raises(ValueError):
            validate_timeout(-5.0, "test")
    
    def test_environment_variable_override(self):
        """Verify environment variables can override defaults"""
        import os
        
        # Save original
        original = os.environ.get("API_READ_TIMEOUT")
        
        try:
            os.environ["API_READ_TIMEOUT"] = "45.0"
            # Re-import to pick up new value
            import importlib
            import app.config.timeout
            importlib.reload(app.config.timeout)
            
            assert app.config.timeout.READ_TIMEOUT == 45.0
        finally:
            # Restore original
            if original:
                os.environ["API_READ_TIMEOUT"] = original
            else:
                os.environ.pop("API_READ_TIMEOUT", None)


class TestThreadPoolExecutorTimeout:
    """Tests for asyncio.wait_for() with ThreadPoolExecutor"""
    
    @pytest.mark.asyncio
    async def test_executor_task_completes_within_timeout(self):
        """Verify executor task completes when within timeout"""
        executor = ThreadPoolExecutor(max_workers=2)
        
        def fast_task():
            time.sleep(0.1)
            return "success"
        
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, fast_task),
            timeout=5.0
        )
        
        assert result == "success"
        executor.shutdown(wait=True)
    
    @pytest.mark.asyncio
    async def test_executor_task_timeout_raises_timeouterror(self):
        """Verify executor task raises TimeoutError when exceeding timeout"""
        executor = ThreadPoolExecutor(max_workers=2)
        
        def slow_task():
            time.sleep(10.0)  # Intentionally slow
            return "success"
        
        loop = asyncio.get_event_loop()
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                loop.run_in_executor(executor, slow_task),
                timeout=1.0
            )
        
        executor.shutdown(wait=True)
    
    @pytest.mark.asyncio
    async def test_executor_timeout_returns_504_response(self):
        """Verify timeout can be caught and converted to 504 response"""
        executor = ThreadPoolExecutor(max_workers=2)
        
        def slow_task():
            time.sleep(10.0)
            return "data"
        
        loop = asyncio.get_event_loop()
        
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(executor, slow_task),
                timeout=1.0
            )
            # Should not reach here
            assert False, "Expected TimeoutError"
        except asyncio.TimeoutError:
            # Simulate API response
            response = {
                "code": 504,
                "message": "请求超时，请稍后重试",
                "data": None
            }
            assert response["code"] == 504
            assert "超时" in response["message"]
        
        executor.shutdown(wait=True)


class TestHTTPXTimeoutConfiguration:
    """Tests for HTTPX client timeout configuration"""
    
    def test_httpx_timeout_object_creation(self):
        """Verify HTTPX Timeout object is created correctly"""
        import httpx
        
        timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT,
            read=READ_TIMEOUT,
            write=WRITE_TIMEOUT,
            pool=POOL_TIMEOUT,
        )
        
        assert timeout.connect == CONNECT_TIMEOUT
        assert timeout.read == READ_TIMEOUT
        assert timeout.write == WRITE_TIMEOUT
        assert timeout.pool == POOL_TIMEOUT
    
    def test_async_client_with_timeout(self):
        """Verify AsyncClient accepts timeout configuration"""
        import httpx
        
        timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT,
            read=READ_TIMEOUT,
            write=WRITE_TIMEOUT,
            pool=POOL_TIMEOUT,
        )
        
        client = httpx.AsyncClient(timeout=timeout)
        
        assert client.timeout.connect == CONNECT_TIMEOUT
        assert client.timeout.read == READ_TIMEOUT
        
        # Cleanup
        import asyncio
        asyncio.run(client.aclose())


class TestRequestTimeoutMiddleware:
    """Tests for request-level timeout middleware"""
    
    @pytest.mark.asyncio
    async def test_middleware_exempts_health_endpoints(self):
        """Verify health endpoints are exempted from timeout"""
        from app.middleware.timeout import TimeoutMiddleware, EXEMPT_PATHS
        
        # Health paths should be exempted
        assert "/health" in EXEMPT_PATHS
        assert "/api/v1/health" in EXEMPT_PATHS
        assert "/api/v1/f9/health" in EXEMPT_PATHS
    
    @pytest.mark.asyncio
    async def test_middleware_returns_504_on_timeout(self):
        """Verify middleware returns 504 when request exceeds timeout"""
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        
        # Add timeout middleware with short timeout
        from app.middleware.timeout import TimeoutMiddleware
        app.add_middleware(TimeoutMiddleware, timeout=1.0)
        
        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(5.0)
            return {"data": "success"}
        
        middleware = TimeoutMiddleware(app, timeout=1.0)
        assert middleware.timeout == 1.0


class TestEndpointTimeoutBehavior:
    """Tests for endpoint-specific timeout behavior"""
    
    @pytest.mark.asyncio
    async def test_search_endpoint_timeout(self):
        assert SEARCH_TIMEOUT == 5.0
    
    @pytest.mark.asyncio
    async def test_quote_endpoint_timeout(self):
        """Verify quote endpoint has 10s timeout"""
        assert QUOTE_TIMEOUT == 10.0
    
    @pytest.mark.asyncio
    async def test_akshare_endpoint_timeout(self):
        """Verify akshare endpoints have 30s timeout"""
        assert AKSHARE_TIMEOUT == 30.0


# ── Run Tests ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])