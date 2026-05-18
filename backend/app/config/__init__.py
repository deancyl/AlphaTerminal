"""
Configuration module for AlphaTerminal backend.

Provides centralized configuration management via:
- settings.py: Pydantic BaseSettings for environment variables
- timeout.py: Timeout configuration for API endpoints
- data_sources.py: Data source registry
"""
from app.config.settings import Settings, get_settings, reload_settings
from app.config.timeout import (
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    WRITE_TIMEOUT,
    POOL_TIMEOUT,
    REQUEST_TIMEOUT,
    AKSHARE_TIMEOUT,
    SEARCH_TIMEOUT,
    QUOTE_TIMEOUT,
    BOND_REFRESH_TIMEOUT,
    MAX_CONNECTIONS,
    MAX_KEEPALIVE_CONNECTIONS,
    KEEPALIVE_EXPIRY,
    get_timeout_config,
    validate_timeout,
)

__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "CONNECT_TIMEOUT",
    "READ_TIMEOUT",
    "WRITE_TIMEOUT",
    "POOL_TIMEOUT",
    "REQUEST_TIMEOUT",
    "AKSHARE_TIMEOUT",
    "SEARCH_TIMEOUT",
    "QUOTE_TIMEOUT",
    "BOND_REFRESH_TIMEOUT",
    "MAX_CONNECTIONS",
    "MAX_KEEPALIVE_CONNECTIONS",
    "KEEPALIVE_EXPIRY",
    "get_timeout_config",
    "validate_timeout",
]
