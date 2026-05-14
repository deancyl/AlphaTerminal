"""
Timeout Configuration

Centralized timeout settings for all API endpoints.
Configurable via environment variables with documented defaults.

Environment Variables:
    API_CONNECT_TIMEOUT: Connection timeout in seconds (default: 5.0)
    API_READ_TIMEOUT: Read timeout in seconds (default: 30.0)
    API_WRITE_TIMEOUT: Write timeout in seconds (default: 10.0)
    API_POOL_TIMEOUT: Pool timeout in seconds (default: 5.0)
    API_REQUEST_TIMEOUT: Global request timeout middleware (default: 60.0)
    AKSHARE_TIMEOUT: Timeout for akshare calls in seconds (default: 30.0)
    SEARCH_TIMEOUT: Timeout for search endpoints (default: 5.0)
    QUOTE_TIMEOUT: Timeout for quote endpoints (default: 10.0)
"""
import os
from typing import Final


# ── HTTP Client Timeout Settings ──────────────────────────────────────────────

CONNECT_TIMEOUT: Final[float] = float(os.getenv("API_CONNECT_TIMEOUT", "5.0"))
READ_TIMEOUT: Final[float] = float(os.getenv("API_READ_TIMEOUT", "30.0"))
WRITE_TIMEOUT: Final[float] = float(os.getenv("API_WRITE_TIMEOUT", "10.0"))
POOL_TIMEOUT: Final[float] = float(os.getenv("API_POOL_TIMEOUT", "5.0"))


# ── Global Request Timeout (Middleware) ────────────────────────────────────────

REQUEST_TIMEOUT: Final[float] = float(os.getenv("API_REQUEST_TIMEOUT", "60.0"))


# ── Endpoint-Specific Timeout Settings ─────────────────────────────────────────

# F9 Deep Data endpoints (akshare calls)
AKSHARE_TIMEOUT: Final[float] = float(os.getenv("AKSHARE_TIMEOUT", "30.0"))

# Search endpoints (should be fast)
SEARCH_TIMEOUT: Final[float] = float(os.getenv("SEARCH_TIMEOUT", "5.0"))

# Quote endpoints (single stock)
QUOTE_TIMEOUT: Final[float] = float(os.getenv("QUOTE_TIMEOUT", "10.0"))

# Convertible bond background refresh
BOND_REFRESH_TIMEOUT: Final[float] = float(os.getenv("BOND_REFRESH_TIMEOUT", "30.0"))


# ── Connection Pool Limits ─────────────────────────────────────────────────────

MAX_CONNECTIONS: Final[int] = int(os.getenv("API_MAX_CONNECTIONS", "100"))
MAX_KEEPALIVE_CONNECTIONS: Final[int] = int(os.getenv("API_MAX_KEEPALIVE", "20"))
KEEPALIVE_EXPIRY: Final[float] = float(os.getenv("API_KEEPALIVE_EXPIRY", "5.0"))


# ── Helper Functions ───────────────────────────────────────────────────────────

def get_timeout_config() -> dict:
    """Return all timeout settings as a dictionary for logging/debugging"""
    return {
        "connect": CONNECT_TIMEOUT,
        "read": READ_TIMEOUT,
        "write": WRITE_TIMEOUT,
        "pool": POOL_TIMEOUT,
        "request": REQUEST_TIMEOUT,
        "akshare": AKSHARE_TIMEOUT,
        "search": SEARCH_TIMEOUT,
        "quote": QUOTE_TIMEOUT,
        "bond_refresh": BOND_REFRESH_TIMEOUT,
        "max_connections": MAX_CONNECTIONS,
        "max_keepalive": MAX_KEEPALIVE_CONNECTIONS,
        "keepalive_expiry": KEEPALIVE_EXPIRY,
    }


def validate_timeout(value: float, name: str, min_val: float = 1.0, max_val: float = 300.0) -> float:
    """
    Validate timeout value is within acceptable range.
    
    Args:
        value: Timeout value to validate
        name: Name of the timeout setting (for error messages)
        min_val: Minimum acceptable value (default: 1.0)
        max_val: Maximum acceptable value (default: 300.0)
    
    Returns:
        Validated timeout value (clamped to range)
    
    Raises:
        ValueError: If value is invalid (negative or non-numeric)
    """
    if value < 0:
        raise ValueError(f"{name} cannot be negative: {value}")
    
    # Clamp to acceptable range
    clamped = max(min_val, min(max_val, value))
    
    if clamped != value:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"{name} clamped from {value} to {clamped}")
    
    return clamped