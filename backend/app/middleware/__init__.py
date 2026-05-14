"""
AlphaTerminal Middleware Package
"""

from .agent_auth import (
    verify_agent_token,
    require_scope,
    audit_middleware,
    get_current_token,
)

from .rate_limit import (
    RateLimitMiddleware,
    RateLimitConfig,
    InMemoryRateLimiter,
    get_limiter,
    get_client_ip,
    create_rate_limit_response,
    add_rate_limit_headers,
    setup_rate_limiting,
)

from .api_key_auth import (
    require_api_key,
    optional_api_key,
    APIKeyAuth,
)

__all__ = [
    "verify_agent_token",
    "require_scope",
    "audit_middleware",
    "get_current_token",
    "require_api_key",
    "optional_api_key",
    "APIKeyAuth",
    "RateLimitMiddleware",
    "RateLimitConfig",
    "InMemoryRateLimiter",
    "get_limiter",
    "get_client_ip",
    "create_rate_limit_response",
    "add_rate_limit_headers",
    "setup_rate_limiting",
]