"""
Macro Module Configuration
Configurable via environment variables
"""
import os
from typing import Final

# Thread pool size for akshare parallel execution
MACRO_THREAD_POOL_SIZE: Final[int] = int(os.getenv("MACRO_THREAD_POOL_SIZE", "8"))

# Cache duration in seconds (default: 5 minutes)
MACRO_CACHE_DURATION: Final[int] = int(os.getenv("MACRO_CACHE_DURATION", "300"))

# Maximum cache entries
MACRO_MAX_CACHE_SIZE: Final[int] = int(os.getenv("MACRO_MAX_CACHE_SIZE", "50"))

# Fetch timeout for overview endpoint (default: 30 seconds)
MACRO_FETCH_TIMEOUT: Final[float] = float(os.getenv("MACRO_FETCH_TIMEOUT", "30.0"))

# Cache cleanup interval in seconds (default: 5 minutes)
MACRO_CLEANUP_INTERVAL: Final[int] = int(os.getenv("MACRO_CLEANUP_INTERVAL", "300"))