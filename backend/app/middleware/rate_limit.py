"""
Rate Limiting Middleware

Implements IP-based rate limiting with Token Bucket algorithm.
Supports burst traffic and smooth rate limiting.

v0.6.61: Migrated from Fixed Window Counter to Token Bucket algorithm.
"""
import time
import logging
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.middleware.rate_limit_token_bucket import TokenBucketRateLimiter, get_token_bucket_limiter

# Use Token Bucket as primary, SQLite Fixed Window as fallback
PrimaryRateLimiter = TokenBucketRateLimiter

from app.config.rate_limit import (
    RateLimitConfig,
    get_limit_for_path,
    is_exempt_path,
)
from app.utils.ip_validation import get_client_ip_safe

logger = logging.getLogger(__name__)


# Token Bucket configuration
# 150 req/min = 2.5 tokens/sec refill rate
DEFAULT_REFILL_RATE = 2.5  # tokens per second
DEFAULT_BURST_CAPACITY = 150  # max burst tokens

# Per-endpoint refill rates (tokens/sec)
# Formula: requests_per_minute / 60 = refill_rate
ENDPOINT_REFILL_RATES = {
    "copilot": 0.5,      # 30 req/min
    "f9_deep": 0.167,    # 10 req/min
    "backtest": 0.083,   # 5 req/min
    "agent": 1.67,       # 100 req/min
    "market": 1.0,       # 60 req/min
    "news": 0.5,         # 30 req/min
    "futures": 1.0,      # 60 req/min
    "macro": 0.5,        # 30 req/min
    "forex": 1.0,        # 60 req/min
    "bond": 0.5,         # 30 req/min
    "market_radar": 0.5, # 30 req/min
    "global_index": 0.5, # 30 req/min
    "default": 3.33,     # 200 req/min
}

# Burst capacities (same as requests_per_minute for simplicity)
ENDPOINT_BURST_CAPACITIES = {
    "copilot": 30,
    "f9_deep": 10,
    "backtest": 5,
    "agent": 100,
    "market": 60,
    "news": 30,
    "futures": 60,
    "macro": 30,
    "forex": 60,
    "bond": 30,
    "market_radar": 30,
    "global_index": 30,
    "default": 200,
}


_limiter: Optional[TokenBucketRateLimiter] = None


def get_limiter() -> TokenBucketRateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = get_token_bucket_limiter()
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


def get_refill_rate_for_category(category: str) -> float:
    """Get refill rate (tokens/sec) for endpoint category."""
    return ENDPOINT_REFILL_RATES.get(category, DEFAULT_REFILL_RATE)


def get_burst_capacity_for_category(category: str) -> int:
    """Get burst capacity for endpoint category."""
    return ENDPOINT_BURST_CAPACITIES.get(category, DEFAULT_BURST_CAPACITY)


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

        # Get category for refill rate and burst capacity
        from app.config.rate_limit import get_endpoint_category
        category = get_endpoint_category(path)
        refill_rate = get_refill_rate_for_category(category)
        burst_capacity = get_burst_capacity_for_category(category)

        key = f"{client_ip}:{path}"

        # Use Token Bucket algorithm
        is_allowed, remaining, limit, reset = self.limiter.is_allowed(
            key,
            refill_rate=refill_rate,
            burst_capacity=burst_capacity
        )

        if not is_allowed:
            retry_after = reset - int(time.time())
            logger.warning(
                f"[RateLimit] Blocked request from {client_ip} to {path} "
                f"(tokens: {remaining}/{burst_capacity}, refill_rate: {refill_rate}/s)"
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
        response.headers["X-RateLimit-Algorithm"] = "token-bucket"

        return response


def setup_rate_limiting(app, config: Optional[RateLimitConfig] = None):
    config = config or RateLimitConfig()
    app.add_middleware(RateLimitMiddleware, config=config)
    logger.info(
        f"[RateLimit] Token Bucket middleware enabled "
        f"(default: {DEFAULT_REFILL_RATE} tokens/s, burst: {DEFAULT_BURST_CAPACITY})"
    )
