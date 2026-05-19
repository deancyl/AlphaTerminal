"""
Rate Limiting Middleware

Implements IP-based rate limiting with endpoint-specific limits.
"""
import time
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.middleware.rate_limit_sqlite import SQLiteRateLimiter

InMemoryRateLimiter = SQLiteRateLimiter

from app.config.rate_limit import (
    RateLimitConfig,
    EndpointLimit,
    get_limit_for_path,
    is_exempt_path,
    ENDPOINT_LIMITS,
)
from app.utils.ip_validation import get_client_ip_safe

logger = logging.getLogger(__name__)


_limiter: Optional[SQLiteRateLimiter] = None


def get_limiter() -> SQLiteRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = SQLiteRateLimiter()
    return _limiter


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    x_real_ip = request.headers.get("x-real-ip")
    remote_addr = request.client.host if request.client else None
    return get_client_ip_safe(x_forwarded_for, x_real_ip, remote_addr)


def create_rate_limit_response(
    retry_after: int,
    limit: int = 0,
    remaining: int = 0,
    reset: int = 0
) -> JSONResponse:
    content = {
        "code": 429,
        "message": "请求过于频繁，请稍后重试",
        "retry_after": retry_after,
        "detail": f"Rate limit exceeded. Try again in {retry_after} seconds."
    }
    
    response = JSONResponse(
        status_code=429,
        content=content,
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset),
        }
    )
    
    return response


def add_rate_limit_headers(
    response: Response,
    limit: int,
    remaining: int,
    reset: int
) -> Response:
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)
    return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.limiter = get_limiter()
    
    async def dispatch(self, request: Request, call_next):
        if not self.config.enabled:
            return await call_next(request)
        
        path = request.url.path
        
        if is_exempt_path(path):
            return await call_next(request)
        
        if request.method == "OPTIONS":
            return await call_next(request)
        
        client_ip = get_client_ip(request)
        endpoint_limit = get_limit_for_path(path)
        
        key = f"{client_ip}:{path}"
        
        is_allowed, remaining, limit, reset = self.limiter.is_allowed(
            key,
            limit=endpoint_limit.requests,
            period=endpoint_limit.period
        )
        
        if not is_allowed:
            retry_after = reset - int(time.time())
            logger.warning(
                f"[RateLimit] Blocked request from {client_ip} to {path} "
                f"(limit: {limit}/{endpoint_limit.period}s)"
            )
            return create_rate_limit_response(
                retry_after=max(1, retry_after),
                limit=limit,
                remaining=remaining,
                reset=reset
            )
        
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        
        return response


def setup_rate_limiting(app, config: Optional[RateLimitConfig] = None):
    config = config or RateLimitConfig()
    app.add_middleware(RateLimitMiddleware, config=config)
    logger.info(f"[RateLimit] Middleware enabled with global limit: {config.global_limit}/{config.global_period}s")
