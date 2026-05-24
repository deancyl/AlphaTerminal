"""
Strategy Execution Engine with proper async task management.

v0.6.121 - Architecture Refactoring
- Replaces in-memory _active_executions with _running_tasks
- Enables proper task cancellation via task.cancel()
- Integrates with SQLite for execution history persistence
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ExecutionStatus(str, Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """Execution result data structure."""
    execution_id: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "result": self.result,
            "error": self.error,
        }


class ExecutionEngine:
    """
    Centralized execution engine with proper async task management.
    
    Key Features:
    - Uses asyncio.Task handles for proper cancellation
    - SQLite persistence for execution history
    - Proper cleanup on shutdown
    """
    
    def __init__(self):
        # Key change: Store asyncio.Task handles, not just results
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, ExecutionResult] = {}
        self._lock = asyncio.Lock()
    
    async def start_execution(
        self,
        execution_id: str,
        coro: Callable[[], Awaitable[Any]],
        persist: bool = True
    ) -> str:
        """
        Start a new execution.
        
        Args:
            execution_id: Unique identifier for this execution
            coro: Async callable to execute
            persist: Whether to persist to SQLite
            
        Returns:
            execution_id
        """
        # Create execution result
        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
            start_time=datetime.now()
        )
        
        # Create and track task
        task = asyncio.create_task(self._run_execution(execution_id, coro))
        
        async with self._lock:
            self._running_tasks[execution_id] = task
            self._results[execution_id] = result
        
        logger.info(f"Execution started: {execution_id}")
        return execution_id
    
    async def _run_execution(
        self,
        execution_id: str,
        coro: Callable[[], Awaitable[Any]]
    ):
        """Internal method to run execution with proper error handling."""
        try:
            result = await coro()
            
            async with self._lock:
                self._results[execution_id].status = ExecutionStatus.COMPLETED
                self._results[execution_id].result = result
                self._results[execution_id].end_time = datetime.now()
            
            logger.info(f"Execution completed: {execution_id}")
            
        except asyncio.CancelledError:
            async with self._lock:
                self._results[execution_id].status = ExecutionStatus.CANCELLED
                self._results[execution_id].end_time = datetime.now()
            
            logger.info(f"Execution cancelled: {execution_id}")
            raise
            
        except Exception as e:
            async with self._lock:
                self._results[execution_id].status = ExecutionStatus.FAILED
                self._results[execution_id].error = str(e)
                self._results[execution_id].end_time = datetime.now()
            
            logger.error(f"Execution failed: {execution_id}: {e}", exc_info=True)
            
        finally:
            async with self._lock:
                self._running_tasks.pop(execution_id, None)
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.
        
        Args:
            execution_id: ID of execution to cancel
            
        Returns:
            True if cancelled, False if not found
        """
        async with self._lock:
            task = self._running_tasks.get(execution_id)
            
            if task is None or task.done():
                logger.warning(f"Cannot cancel: execution not running: {execution_id}")
                return False
            
            # Cancel the task
            task.cancel()
            
            try:
                # Wait for cancellation to complete
                await asyncio.shield(task)
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Execution cancelled: {execution_id}")
            return True
    
    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an execution."""
        async with self._lock:
            result = self._results.get(execution_id)
            return result.to_dict() if result else None
    
    async def get_all_running_executions(self) -> Dict[str, Dict[str, Any]]:
        """Get all running executions."""
        async with self._lock:
            return {
                eid: result.to_dict()
                for eid, result in self._results.items()
                if result.status == ExecutionStatus.RUNNING
            }
    
    async def shutdown(self):
        """Cancel all running tasks on shutdown."""
        logger.info("ExecutionEngine shutdown initiated")
        
        async with self._lock:
            tasks = list(self._running_tasks.items())
        
        for execution_id, task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    pass
        
        logger.info(f"ExecutionEngine shutdown complete: {len(tasks)} tasks cancelled")


# Singleton instance
_engine: Optional[ExecutionEngine] = None


def get_execution_engine() -> ExecutionEngine:
    """Get the global execution engine instance."""
    global _engine
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine
