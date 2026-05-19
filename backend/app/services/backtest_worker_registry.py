"""
Backtest Worker Registry - Track and monitor running backtest workers.

This module provides a singleton registry to track all active backtest workers,
collect real-time CPU/memory metrics, and allow killing runaway processes.
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
import threading

logger = logging.getLogger(__name__)

# Try to import psutil for CPU/memory monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("[BacktestWorkerRegistry] psutil not installed, CPU/memory metrics will be unavailable")


@dataclass
class BacktestWorker:
    """Represents a running backtest worker."""
    id: str
    task: asyncio.Task
    symbol: str
    strategy_type: str
    start_time: float
    status: str = "running"  # running, completed, cancelled, failed
    progress: float = 0.0  # 0.0 to 1.0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    thread_id: Optional[int] = None
    _last_cpu_check: float = field(default_factory=time.time)
    _cpu_samples: List[float] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def duration_str(self) -> str:
        """Get human-readable duration."""
        seconds = self.duration_seconds
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"


class BacktestWorkerRegistry:
    """
    Singleton registry to track running backtest workers.
    
    Features:
    - Register/unregister workers
    - Get real-time CPU/memory metrics
    - Kill runaway workers
    - WebSocket streaming support
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._workers: Dict[str, BacktestWorker] = {}
        self._workers_lock = threading.Lock()
        self._ws_clients: List[Any] = []  # WebSocket clients for broadcasting
        self._process = psutil.Process() if HAS_PSUTIL else None
        logger.info("[BacktestWorkerRegistry] Initialized")
    
    def register(
        self,
        task: asyncio.Task,
        symbol: str,
        strategy_type: str,
        worker_id: Optional[str] = None
    ) -> str:
        """
        Register a new backtest worker.
        
        Args:
            task: The asyncio.Task running the backtest
            symbol: Stock symbol being backtested
            strategy_type: Strategy type (ma_crossover, rsi_oversold, etc.)
            worker_id: Optional custom ID (auto-generated if None)
        
        Returns:
            The worker ID
        """
        if worker_id is None:
            worker_id = f"bt_{uuid.uuid4().hex[:8]}"
        
        worker = BacktestWorker(
            id=worker_id,
            task=task,
            symbol=symbol,
            strategy_type=strategy_type,
            start_time=time.time(),
            thread_id=threading.current_thread().ident
        )
        
        with self._workers_lock:
            self._workers[worker_id] = worker
        
        # Add done callback to auto-unregister
        task.add_done_callback(lambda t: self._on_task_done(worker_id, t))
        
        logger.info(f"[BacktestWorkerRegistry] Registered worker {worker_id} for {symbol} ({strategy_type})")
        return worker_id
    
    def _on_task_done(self, worker_id: str, task: asyncio.Task):
        """Callback when task completes."""
        with self._workers_lock:
            worker = self._workers.get(worker_id)
            if not worker:
                return
            
            try:
                result = task.result()
                worker.status = "completed"
                worker.result = result
                worker.progress = 1.0
            except asyncio.CancelledError:
                worker.status = "cancelled"
            except Exception as e:
                worker.status = "failed"
                worker.error = str(e)
            
            logger.info(f"[BacktestWorkerRegistry] Worker {worker_id} finished with status: {worker.status}")
    
    def unregister(self, worker_id: str):
        """Unregister a completed worker."""
        with self._workers_lock:
            if worker_id in self._workers:
                del self._workers[worker_id]
                logger.info(f"[BacktestWorkerRegistry] Unregistered worker {worker_id}")
    
    def update_progress(self, worker_id: str, progress: float):
        """Update progress for a running worker."""
        with self._workers_lock:
            worker = self._workers.get(worker_id)
            if worker:
                worker.progress = max(0.0, min(1.0, progress))
    
    def get_worker(self, worker_id: str) -> Optional[BacktestWorker]:
        """Get a specific worker by ID."""
        with self._workers_lock:
            return self._workers.get(worker_id)
    
    def get_all_workers(self) -> List[BacktestWorker]:
        """Get all workers."""
        with self._workers_lock:
            return list(self._workers.values())
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """
        Get metrics for all workers.
        
        Returns:
            List of worker metrics with CPU/memory usage
        """
        metrics = []
        current_time = time.time()
        
        with self._workers_lock:
            for worker in self._workers.values():
                cpu_percent = 0.0
                memory_mb = 0.0
                
                if HAS_PSUTIL and self._process:
                    try:
                        # Get CPU percent (non-blocking, uses last sample)
                        cpu_percent = self._process.cpu_percent(interval=None)
                        
                        # Get memory info
                        mem_info = self._process.memory_info()
                        memory_mb = mem_info.rss / (1024 * 1024)
                        
                        # Sample CPU for averaging
                        if current_time - worker._last_cpu_check >= 1.0:
                            worker._cpu_samples.append(cpu_percent)
                            if len(worker._cpu_samples) > 10:
                                worker._cpu_samples.pop(0)
                            worker._last_cpu_check = current_time
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                avg_cpu = sum(worker._cpu_samples) / len(worker._cpu_samples) if worker._cpu_samples else 0.0
                
                metrics.append({
                    "id": worker.id,
                    "symbol": worker.symbol,
                    "strategy_type": worker.strategy_type,
                    "status": worker.status,
                    "progress": round(worker.progress * 100, 1),
                    "duration_seconds": round(worker.duration_seconds, 1),
                    "duration_str": worker.duration_str,
                    "cpu_percent": round(cpu_percent, 1),
                    "avg_cpu_percent": round(avg_cpu, 1),
                    "memory_mb": round(memory_mb, 1),
                    "start_time": datetime.fromtimestamp(worker.start_time).isoformat(),
                    "error": worker.error
                })
        
        return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all workers."""
        metrics = self.get_metrics()
        
        if not metrics:
            return {
                "total_workers": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "total_cpu_percent": 0.0,
                "total_memory_mb": 0.0
            }
        
        running = sum(1 for m in metrics if m["status"] == "running")
        completed = sum(1 for m in metrics if m["status"] == "completed")
        failed = sum(1 for m in metrics if m["status"] == "failed")
        cancelled = sum(1 for m in metrics if m["status"] == "cancelled")
        
        return {
            "total_workers": len(metrics),
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "total_cpu_percent": round(sum(m["cpu_percent"] for m in metrics), 1),
            "total_memory_mb": round(sum(m["memory_mb"] for m in metrics), 1)
        }
    
    async def kill(self, worker_id: str) -> bool:
        """
        Kill a specific worker.
        
        Args:
            worker_id: The worker ID to kill
        
        Returns:
            True if killed successfully, False otherwise
        """
        with self._workers_lock:
            worker = self._workers.get(worker_id)
            if not worker:
                logger.warning(f"[BacktestWorkerRegistry] Worker {worker_id} not found")
                return False
            
            if worker.status != "running":
                logger.warning(f"[BacktestWorkerRegistry] Worker {worker_id} is not running (status: {worker.status})")
                return False
            
            try:
                # Cancel the asyncio task
                worker.task.cancel()
                worker.status = "cancelled"
                logger.info(f"[BacktestWorkerRegistry] Killed worker {worker_id}")
                return True
            except Exception as e:
                logger.error(f"[BacktestWorkerRegistry] Failed to kill worker {worker_id}: {e}")
                return False
    
    def cleanup_completed(self, max_age_seconds: int = 300):
        """
        Remove completed/failed workers older than max_age_seconds.
        
        Args:
            max_age_seconds: Maximum age in seconds (default 5 minutes)
        """
        current_time = time.time()
        to_remove = []
        
        with self._workers_lock:
            for worker_id, worker in self._workers.items():
                if worker.status in ("completed", "failed", "cancelled"):
                    if current_time - worker.start_time > max_age_seconds:
                        to_remove.append(worker_id)
            
            for worker_id in to_remove:
                del self._workers[worker_id]
        
        if to_remove:
            logger.info(f"[BacktestWorkerRegistry] Cleaned up {len(to_remove)} old workers")
    
    def add_ws_client(self, client):
        """Add a WebSocket client for broadcasting."""
        self._ws_clients.append(client)
    
    def remove_ws_client(self, client):
        """Remove a WebSocket client."""
        if client in self._ws_clients:
            self._ws_clients.remove(client)
    
    async def broadcast_metrics(self):
        """Broadcast metrics to all WebSocket clients."""
        if not self._ws_clients:
            return
        
        metrics = self.get_metrics()
        summary = self.get_summary()
        
        message = {
            "type": "backtest_metrics",
            "timestamp": datetime.now().isoformat(),
            "workers": metrics,
            "summary": summary
        }
        
        for client in self._ws_clients[:]:  # Copy to avoid modification during iteration
            try:
                await client.send_json(message)
            except Exception as e:
                logger.warning(f"[BacktestWorkerRegistry] Failed to send to WS client: {e}")
                self.remove_ws_client(client)


# Singleton instance
_registry = None


def get_backtest_registry() -> BacktestWorkerRegistry:
    """Get the singleton BacktestWorkerRegistry instance."""
    global _registry
    if _registry is None:
        _registry = BacktestWorkerRegistry()
    return _registry
