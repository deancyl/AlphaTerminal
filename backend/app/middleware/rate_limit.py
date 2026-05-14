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

from app.config.rate_limit import (
    RateLimitConfig,
    EndpointLimit,
    get_limit_for_path,
    is_exempt_path,
    ENDPOINT_LIMITS,
)

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    count: int = 0
    reset_at: float = 0.0
    first_request: float = 0.0


class InMemoryRateLimiter:
    def __init__(self):
        self._storage: Dict[str, RateLimitEntry] = {}
    
    def is_allowed(self, key: str, limit: int, period: int) -> Tuple[bool, int, int, int]:
        now = time.time()
        
        if key not in self._storage:
            self._storage[key] = RateLimitEntry(
                count=1,
                reset_at=now + period,
                first_request=now
            )
            return True, limit - 1, limit, int(self._storage[key].reset_at)
        
        entry = self._storage[key]
        
        if now > entry.reset_at:
            entry.count = 1
            entry.reset_at = now + period
            entry.first_request = now
            return True, limit - 1, limit, int(entry.reset_at)
        
        if entry.count >= limit:
            retry_after = int(entry.reset_at - now)
            return False, 0, limit, int(entry.reset_at)
        
        entry.count += 1
        return True, limit - entry.count, limit, int(entry.reset_at)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_keys": len(self._storage),
            "entries": {
                k: {"count": v.count, "reset_at": v.reset_at}
                for k, v in list(self._storage.items())[:100]
            }
        }
    
    def reset(self, key: Optional[str] = None):
        if key:
            self._storage.pop(key, None)
        else:
            self._storage.clear()


_limiter: Optional[InMemoryRateLimiter] = None


def get_limiter() -> InMemoryRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = InMemoryRateLimiter()
    return _limiter


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    
    if request.client:
        return request.client.host
    
    return "unknown"


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
