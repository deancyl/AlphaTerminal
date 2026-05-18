"""
Request Timeout Middleware

Global request timeout protection for all API endpoints.
Returns 504 Gateway Timeout when requests exceed the configured timeout.

Health check endpoints are exempted from timeout to allow monitoring.
"""
import asyncio
import logging
from typing import Callable, List, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.timeout import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

EXEMPT_PATHS: List[str] = [
    "/health",
    "/api/v1/health",
    "/api/v1/macro/health",
    "/api/v1/f9/health",
    "/api/v1/agent/health",
    "/docs",
    "/openapi.json",
    "/redoc",
]


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces a global request timeout.
    
    If a request exceeds the timeout, returns 504 Gateway Timeout.
    Health check endpoints are exempted.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        timeout: Optional[float] = None,
        exempt_paths: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.timeout = timeout or REQUEST_TIMEOUT
        self.exempt_paths = exempt_paths or EXEMPT_PATHS
    
    def _is_exempt(self, path: str) -> bool:
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        return False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)
        
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[TimeoutMiddleware] Request {request.method} {request.url.path} "
                f"exceeded {self.timeout}s timeout"
            )
            return JSONResponse(
                status_code=504,
                content={
                    "code": 504,
                    "message": f"请求超时（{self.timeout}秒），请稍后重试",
                    "data": None,
                }
            )
        except Exception as e:
            logger.error(f"[TimeoutMiddleware] Unexpected error: {e}")
            raise