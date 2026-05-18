"""
Async Database Operations Wrapper

Wraps synchronous database functions with async interfaces using ThreadPoolExecutor.
Provides timeout protection and non-blocking I/O for FastAPI endpoints.

Usage:
    from app.db.async_db import async_get_session, async_get_latest_prices
    
    # In async endpoint
    session = await async_get_session(session_id)
    prices = await async_get_latest_prices(symbols=['sh600519', 'sz000001'])
"""
import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypeVar,
    ParamSpec,
    overload,
)

# Import timeout configuration
from app.config.timeout import READ_TIMEOUT

logger = logging.getLogger(__name__)

# ── Shared Thread Pool for Database Operations ──────────────────────────────────
# Max 50 concurrent DB operations (SQLite handles concurrency via WAL mode)
_db_executor: ThreadPoolExecutor = ThreadPoolExecutor(
    max_workers=50,
    thread_name_prefix="db_worker"
)

# Default timeout for database operations (30 seconds)
DEFAULT_DB_TIMEOUT: float = 30.0


# ── Type Variables for Generic Decorator ───────────────────────────────────────
P = ParamSpec('P')
R = TypeVar('R')


# ── Async Wrapper Decorator ────────────────────────────────────────────────────
def async_wrap(
    sync_func: Callable[P, R],
    timeout: float = DEFAULT_DB_TIMEOUT,
    executor: Optional[ThreadPoolExecutor] = None
) -> Callable[P, asyncio.Future[R]]:
    """
    Wrap a synchronous function to run asynchronously in a thread pool.
    
    Args:
        sync_func: The synchronous function to wrap
        timeout: Maximum execution time in seconds (default: 30s)
        executor: Custom ThreadPoolExecutor (default: shared _db_executor)
    
    Returns:
        Async function that runs sync_func in thread pool with timeout
    
    Example:
        async_get_session = async_wrap(get_session, timeout=30.0)
        result = await async_get_session(session_id="abc123")
    
    Raises:
        asyncio.TimeoutError: If execution exceeds timeout
        Exception: Re-raises any exception from sync_func
    """
    @functools.wraps(sync_func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        loop = asyncio.get_event_loop()
        exec_pool = executor or _db_executor
        
        # Run sync function in thread pool
        future = loop.run_in_executor(
            exec_pool,
            functools.partial(sync_func, *args, **kwargs)
        )
        
        # Apply timeout
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                f"[AsyncDB] Timeout after {timeout}s in {sync_func.__name__}"
            )
            raise
        except Exception as e:
            logger.error(
                f"[AsyncDB] Error in {sync_func.__name__}: {type(e).__name__}: {e}"
            )
            raise
    
    return wrapper


# ── Database Functions (from database.py) ─────────────────────────────────────

# Import sync functions
from app.db.database import (
    get_latest_prices,
    get_daily_history,
    get_daily_count,
    get_periodic_history,
    get_periodic_count,
    search_stocks,
    get_all_stocks,
)

# Async wrappers for database.py functions
async_get_latest_prices = async_wrap(get_latest_prices, timeout=READ_TIMEOUT)
async_get_daily_history = async_wrap(get_daily_history, timeout=READ_TIMEOUT)
async_get_daily_count = async_wrap(get_daily_count, timeout=READ_TIMEOUT)
async_get_periodic_history = async_wrap(get_periodic_history, timeout=READ_TIMEOUT)
async_get_periodic_count = async_wrap(get_periodic_count, timeout=READ_TIMEOUT)
async_search_stocks = async_wrap(search_stocks, timeout=READ_TIMEOUT)
async_get_all_stocks = async_wrap(get_all_stocks, timeout=READ_TIMEOUT)


# ── Session Functions (from session_db.py) ────────────────────────────────────

from app.db.session_db import (
    create_session,
    get_session,
    update_session_activity,
    delete_session,
)

# Async wrappers for session_db.py functions
async_create_session = async_wrap(create_session, timeout=DEFAULT_DB_TIMEOUT)
async_get_session = async_wrap(get_session, timeout=DEFAULT_DB_TIMEOUT)
async_update_session_activity = async_wrap(update_session_activity, timeout=DEFAULT_DB_TIMEOUT)
async_delete_session = async_wrap(delete_session, timeout=DEFAULT_DB_TIMEOUT)


# ── Model Config Functions (from model_config_db.py) ────────────────────────────

from app.db.model_config_db import (
    get_model_config,
    set_model_config,
    get_all_model_configs,
)

# Async wrappers for model_config_db.py functions
async_get_model_config = async_wrap(get_model_config, timeout=DEFAULT_DB_TIMEOUT)
async_set_model_config = async_wrap(set_model_config, timeout=DEFAULT_DB_TIMEOUT)
async_get_all_model_configs = async_wrap(get_all_model_configs, timeout=DEFAULT_DB_TIMEOUT)


# ── Convenience Exports ───────────────────────────────────────────────────────

__all__ = [
    # Decorator
    'async_wrap',
    
    # Thread pool
    '_db_executor',
    
    # Timeout
    'DEFAULT_DB_TIMEOUT',
    
    # Database async functions
    'async_get_latest_prices',
    'async_get_daily_history',
    'async_get_daily_count',
    'async_get_periodic_history',
    'async_get_periodic_count',
    'async_search_stocks',
    'async_get_all_stocks',
    
    # Session async functions
    'async_create_session',
    'async_get_session',
    'async_update_session_activity',
    'async_delete_session',
    
    # Model config async functions
    'async_get_model_config',
    'async_set_model_config',
    'async_get_all_model_configs',
]


# ── Cleanup Function ───────────────────────────────────────────────────────────

def shutdown_db_executor(wait: bool = True) -> None:
    """
    Shutdown the database thread pool executor.
    
    Call this during application shutdown to cleanly release resources.
    
    Args:
        wait: If True, wait for pending tasks to complete
    """
    _db_executor.shutdown(wait=wait)
    logger.info("[AsyncDB] Executor shutdown complete")
