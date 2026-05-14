"""
Rate Limiting Configuration

Defines rate limits for different endpoint categories.
"""
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class EndpointLimit:
    requests: int
    period: int


ENDPOINT_LIMITS = {
    "f9_deep": EndpointLimit(requests=10, period=60),
    "backtest": EndpointLimit(requests=5, period=60),
    "agent": EndpointLimit(requests=100, period=60),
    "market": EndpointLimit(requests=60, period=60),
    "news": EndpointLimit(requests=30, period=60),
    "futures": EndpointLimit(requests=60, period=60),
    "default": EndpointLimit(requests=200, period=60),
}

EXEMPT_PATHS = [
    "/health",
    "/api/v1/health",
    "/api/v1/f9/health",
    "/api/agent/v1/health",
    "/api/v1/macro/health",
]


@dataclass
class RateLimitConfig:
    global_limit: int = 200
    global_period: int = 60
    enabled: bool = True
    storage_uri: Optional[str] = None
    
    def __post_init__(self):
        if self.enabled is None:
            self.enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
        
        env_limit = os.environ.get("RATE_LIMIT_GLOBAL")
        if env_limit:
            self.global_limit = int(env_limit)
        
        env_period = os.environ.get("RATE_LIMIT_PERIOD")
        if env_period:
            self.global_period = int(env_period)


def get_endpoint_category(path: str) -> str:
    if "/f9/" in path:
        return "f9_deep"
    if "/backtest/" in path:
        return "backtest"
    if "/agent/" in path:
        return "agent"
    if "/futures/" in path:
        return "futures"
    if "/market/" in path or "/stocks/" in path:
        return "market"
    if "/news/" in path:
        return "news"
    return "default"


def get_limit_for_path(path: str) -> EndpointLimit:
    category = get_endpoint_category(path)
    return ENDPOINT_LIMITS.get(category, ENDPOINT_LIMITS["default"])


def is_exempt_path(path: str) -> bool:
    path_lower = path.lower().rstrip("/")
    for exempt in EXEMPT_PATHS:
        if path_lower == exempt.lower().rstrip("/"):
            return True
        if path_lower.startswith(exempt.lower().rstrip("/") + "/"):
            return True
    return False
