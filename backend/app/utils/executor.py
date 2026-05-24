"""
Centralized ThreadPoolExecutor for AlphaTerminal.
Replaces 43 fragmented executor instances across the codebase.

v0.6.103 - Architecture Refactoring
"""
from concurrent.futures import ThreadPoolExecutor
import atexit
import logging
import os

logger = logging.getLogger(__name__)

# Configuration - matches Python 3.8+ default formula
MAX_WORKERS = min(32, (os.cpu_count() or 4) + 4)
FAST_MAX_WORKERS = min(16, (os.cpu_count() or 4) + 2)

# Global executor instances
_executor: ThreadPoolExecutor = None
_fast_executor: ThreadPoolExecutor = None


def _init_executor():
    """Initialize global executors."""
    global _executor, _fast_executor
    
    if _executor is not None:
        return
    
    _executor = ThreadPoolExecutor(
        max_workers=MAX_WORKERS,
        thread_name_prefix="alpha_io_"
    )
    
    _fast_executor = ThreadPoolExecutor(
        max_workers=FAST_MAX_WORKERS,
        thread_name_prefix="alpha_fast_"
    )
    
    logger.info(f"ThreadPoolExecutor initialized: io={MAX_WORKERS} workers, fast={FAST_MAX_WORKERS} workers")


def get_executor(fast: bool = False) -> ThreadPoolExecutor:
    """
    Get the global executor instance.
    
    Args:
        fast: If True, returns the fast executor for sub-second operations.
              If False, returns the main I/O executor.
    
    Returns:
        ThreadPoolExecutor instance
    """
    _init_executor()
    return _fast_executor if fast else _executor


def shutdown_executor():
    """Shutdown all executors gracefully."""
    global _executor, _fast_executor
    
    logger.info("ThreadPoolExecutor shutdown initiated")
    
    if _executor is not None:
        _executor.shutdown(wait=True, cancel_futures=False)
        _executor = None
    
    if _fast_executor is not None:
        _fast_executor.shutdown(wait=True, cancel_futures=False)
        _fast_executor = None
    
    logger.info("ThreadPoolExecutor shutdown complete")


# Register cleanup on exit
atexit.register(shutdown_executor)
