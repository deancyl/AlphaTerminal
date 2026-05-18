"""
ExecutorManager - Centralized Lifecycle Management for All Executors

This module provides a unified manager for tracking and gracefully shutting down
all active executors in the AlphaTerminal backend, preventing resource leaks.

Supported Executors:
  - BacktestEngine: Backtest execution engine
  - StrategyExecutionEngine: Strategy execution engine
  - AgentJobQueue: Agent job queue system
  - MCP Server: Model Context Protocol server
  - Research Service: Research report service

Usage:
    from app.services.executor_manager import executor_manager
    
    # Register executor
    executor_manager.register("backtest", backtest_engine)
    
    # Get executor
    engine = executor_manager.get("backtest")
    
    # Graceful shutdown
    await executor_manager.shutdown_all()
    
    # Get status
    status = executor_manager.get_status()

Author: AlphaTerminal Team
Version: 0.6.35
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class ExecutorStatus(Enum):
    """Executor status"""
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ExecutorInfo:
    """Executor information"""
    name: str
    status: ExecutorStatus
    registered_at: datetime
    instance: Any
    shutdown_method: Optional[str] = None
    last_activity: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "status": self.status.value,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "shutdown_method": self.shutdown_method,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class ExecutorManager:
    """
    Centralized Executor Manager
    
    Features:
    - Register and track all active executors
    - Graceful shutdown for all registered executors
    - Track execution status and metrics
    - Prevent resource leaks
    
    Thread-safe singleton implementation.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._executors: Dict[str, ExecutorInfo] = {}
        self._shutdown_timeout = 30.0  # seconds
        self._initialized = True
        
        logger.info("[ExecutorManager] Initialized")
    
    def register(
        self,
        name: str,
        executor: Any,
        shutdown_method: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register an executor.
        
        Args:
            name: Unique executor name
            executor: Executor instance
            shutdown_method: Method name to call for shutdown (default: auto-detect)
            metadata: Additional metadata
            
        Returns:
            True if registered successfully, False if already exists
        """
        if name in self._executors:
            logger.warning(f"[ExecutorManager] Executor '{name}' already registered")
            return False
        
        # Auto-detect shutdown method
        if shutdown_method is None:
            shutdown_method = self._detect_shutdown_method(executor)
        
        executor_info = ExecutorInfo(
            name=name,
            status=ExecutorStatus.IDLE,
            registered_at=datetime.now(),
            instance=executor,
            shutdown_method=shutdown_method,
            metadata=metadata or {},
        )
        
        self._executors[name] = executor_info
        
        logger.info(f"[ExecutorManager] Registered executor: {name} (shutdown: {shutdown_method})")
        
        return True
    
    def unregister(self, name: str) -> bool:
        """
        Unregister an executor (does not shutdown).
        
        Args:
            name: Executor name
            
        Returns:
            True if unregistered, False if not found
        """
        if name not in self._executors:
            logger.warning(f"[ExecutorManager] Executor '{name}' not found")
            return False
        
        del self._executors[name]
        logger.info(f"[ExecutorManager] Unregistered executor: {name}")
        return True
    
    def get(self, name: str) -> Optional[Any]:
        """
        Get executor instance by name.
        
        Args:
            name: Executor name
            
        Returns:
            Executor instance or None if not found
        """
        executor_info = self._executors.get(name)
        return executor_info.instance if executor_info else None
    
    def get_info(self, name: str) -> Optional[ExecutorInfo]:
        """
        Get executor info by name.
        
        Args:
            name: Executor name
            
        Returns:
            ExecutorInfo or None if not found
        """
        return self._executors.get(name)
    
    def update_status(self, name: str, status: ExecutorStatus, error_message: Optional[str] = None):
        """
        Update executor status.
        
        Args:
            name: Executor name
            status: New status
            error_message: Error message if status is ERROR
        """
        if name not in self._executors:
            logger.warning(f"[ExecutorManager] Cannot update status: executor '{name}' not found")
            return
        
        executor_info = self._executors[name]
        executor_info.status = status
        executor_info.last_activity = datetime.now()
        
        if error_message:
            executor_info.error_message = error_message
        
        logger.debug(f"[ExecutorManager] Updated status for '{name}': {status.value}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all executors.
        
        Returns:
            Dict with executor status information
        """
        executors_status = {
            name: info.to_dict()
            for name, info in self._executors.items()
        }
        
        return {
            "total_executors": len(self._executors),
            "executors": executors_status,
            "shutdown_timeout": self._shutdown_timeout,
        }
    
    async def shutdown_executor(self, name: str, timeout: Optional[float] = None) -> bool:
        """
        Shutdown a specific executor.
        
        Args:
            name: Executor name
            timeout: Shutdown timeout in seconds (default: use class default)
            
        Returns:
            True if shutdown successfully, False otherwise
        """
        if name not in self._executors:
            logger.warning(f"[ExecutorManager] Cannot shutdown: executor '{name}' not found")
            return False
        
        executor_info = self._executors[name]
        
        if executor_info.status == ExecutorStatus.STOPPED:
            logger.info(f"[ExecutorManager] Executor '{name}' already stopped")
            return True
        
        executor_info.status = ExecutorStatus.STOPPING
        timeout = timeout or self._shutdown_timeout
        
        logger.info(f"[ExecutorManager] Shutting down executor: {name} (timeout: {timeout}s)")
        
        try:
            instance = executor_info.instance
            shutdown_method = executor_info.shutdown_method
            
            if shutdown_method and hasattr(instance, shutdown_method):
                method = getattr(instance, shutdown_method)
                
                # Check if method is async
                if asyncio.iscoroutinefunction(method):
                    await asyncio.wait_for(method(), timeout=timeout)
                else:
                    # Run sync method in executor
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, method)
            
            executor_info.status = ExecutorStatus.STOPPED
            executor_info.last_activity = datetime.now()
            
            logger.info(f"[ExecutorManager] Executor '{name}' shutdown successfully")
            return True
            
        except asyncio.TimeoutError:
            error_msg = f"Shutdown timeout after {timeout}s"
            executor_info.status = ExecutorStatus.ERROR
            executor_info.error_message = error_msg
            logger.error(f"[ExecutorManager] {error_msg} for executor '{name}'")
            return False
            
        except Exception as e:
            error_msg = f"Shutdown error: {str(e)}"
            executor_info.status = ExecutorStatus.ERROR
            executor_info.error_message = error_msg
            logger.error(f"[ExecutorManager] {error_msg} for executor '{name}'", exc_info=True)
            return False
    
    async def shutdown_all(self, timeout: Optional[float] = None) -> Dict[str, bool]:
        """
        Shutdown all registered executors.
        
        Args:
            timeout: Shutdown timeout per executor in seconds
            
        Returns:
            Dict mapping executor names to shutdown success status
        """
        logger.info(f"[ExecutorManager] Shutting down all executors ({len(self._executors)} total)")
        
        results = {}
        
        # Shutdown in reverse order of registration (LIFO)
        executor_names = list(self._executors.keys())[::-1]
        
        for name in executor_names:
            success = await self.shutdown_executor(name, timeout=timeout)
            results[name] = success
        
        # Summary
        successful = sum(1 for v in results.values() if v)
        total = len(results)
        
        logger.info(f"[ExecutorManager] Shutdown complete: {successful}/{total} successful")
        
        return results
    
    def _detect_shutdown_method(self, executor: Any) -> Optional[str]:
        """
        Auto-detect shutdown method for an executor.
        
        Args:
            executor: Executor instance
            
        Returns:
            Method name or None if not found
        """
        # Common shutdown method names (in priority order)
        shutdown_methods = [
            "shutdown",
            "stop",
            "close",
            "cleanup",
            "destroy",
            "teardown",
        ]
        
        for method_name in shutdown_methods:
            if hasattr(executor, method_name):
                return method_name
        
        return None
    
    def set_shutdown_timeout(self, timeout: float):
        """
        Set default shutdown timeout.
        
        Args:
            timeout: Timeout in seconds
        """
        self._shutdown_timeout = timeout
        logger.info(f"[ExecutorManager] Shutdown timeout set to {timeout}s")


# Global singleton instance
executor_manager = ExecutorManager()


# Convenience functions
def get_executor_manager() -> ExecutorManager:
    """Get the global ExecutorManager instance."""
    return executor_manager


def register_executor(name: str, executor: Any, **kwargs) -> bool:
    """Register an executor with the global manager."""
    return executor_manager.register(name, executor, **kwargs)


def get_executor(name: str) -> Optional[Any]:
    """Get an executor by name."""
    return executor_manager.get(name)


async def shutdown_all_executors(timeout: Optional[float] = None) -> Dict[str, bool]:
    """Shutdown all executors."""
    return await executor_manager.shutdown_all(timeout=timeout)
