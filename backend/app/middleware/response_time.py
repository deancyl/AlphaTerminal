"""
Response Time Middleware for API Monitoring

Tracks response time for all API endpoints and integrates with cache_metrics.
"""

import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.cache_metrics import get_cache_metrics

logger = logging.getLogger(__name__)


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API response time and record metrics.
    
    Features:
    - Uses time.perf_counter() for precise timing
    - Tracks: endpoint path, HTTP method, response_time_ms, status_code
    - Skips health/metrics endpoints to avoid recursion
    - Adds X-Response-Time header to responses
    - Records metrics to cache_metrics for monitoring
    """
    
    # Endpoints to skip (avoid recursion and noise)
    SKIP_PATHS = {
        '/api/v1/health',
        '/health',
        '/metrics',
        '/api/v1/metrics',
        '/favicon.ico',
        '/',
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request and track response time."""
        
        # Skip certain endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        # Skip static files
        if request.url.path.startswith('/assets/'):
            return await call_next(request)
        
        # Skip WebSocket upgrades
        if request.headers.get('upgrade', '').lower() == 'websocket':
            return await call_next(request)
        
        # Record start time using perf_counter for precision
        start_time = time.perf_counter()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration in milliseconds
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Extract metrics
        endpoint = request.url.path
        method = request.method
        status_code = response.status_code
        
        # Record to cache_metrics
        try:
            get_cache_metrics().record_api_latency(
                endpoint=endpoint,
                method=method,
                latency_ms=duration_ms,
                status_code=status_code
            )
        except Exception as e:
            logger.warning(f"[ResponseTimeMiddleware] Failed to record Prometheus metrics: {e}")
        
        # Record to SQLite for historical queries
        try:
            from app.db.metrics_db import record_metric
            record_metric(endpoint, method, duration_ms, status_code)
        except Exception as e:
            logger.warning(f"[ResponseTimeMiddleware] Failed to record SQLite metrics: {e}")
        
        # Add response time header
        response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"
        
        return response
