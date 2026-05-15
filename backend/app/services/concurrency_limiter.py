"""
Concurrency Limiter Service

Per-model concurrency limiting with queue management.

Key Features:
- Per-model semaphore-based limiting
- Queue management with timeout
- Metrics tracking (active, queued, rejected)
- Dynamic limit updates
"""
import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from threading import RLock

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT = 10
DEFAULT_TIMEOUT = 30.0


@dataclass
class ModelMetrics:
    """Per-model concurrency metrics"""
    model_key: str
    max_concurrent: int
    active: int = 0
    queued: int = 0
    rejected: int = 0
    total_requests: int = 0
    total_acquired: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_key": self.model_key,
            "max_concurrent": self.max_concurrent,
            "active": self.active,
            "queued": self.queued,
            "rejected": self.rejected,
            "total_requests": self.total_requests,
            "total_acquired": self.total_acquired,
            "utilization": self.active / self.max_concurrent if self.max_concurrent > 0 else 0
        }


class ConcurrencyLimiter:
    """
    Per-model concurrency limiter using semaphores.
    
    Features:
    - Async semaphore per model
    - Queue with timeout
    - Metrics tracking
    """
    
    def __init__(self):
        self._lock = RLock()
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._limits: Dict[str, int] = {}
        self._metrics: Dict[str, ModelMetrics] = {}
        
        logger.info("[ConcurrencyLimiter] Initialized")
    
    def _get_model_key(self, provider: str, model_id: str) -> str:
        return f"{provider}:{model_id}"
    
    def _ensure_semaphore(self, model_key: str, max_concurrent: int = DEFAULT_MAX_CONCURRENT):
        """Ensure semaphore exists for model"""
        with self._lock:
            if model_key not in self._semaphores:
                try:
                    loop = asyncio.get_event_loop()
                    self._semaphores[model_key] = asyncio.Semaphore(max_concurrent)
                except RuntimeError:
                    self._semaphores[model_key] = asyncio.Semaphore(max_concurrent)
                
                self._limits[model_key] = max_concurrent
                self._metrics[model_key] = ModelMetrics(
                    model_key=model_key,
                    max_concurrent=max_concurrent
                )
    
    async def acquire(
        self,
        provider: str,
        model_id: str,
        timeout: float = DEFAULT_TIMEOUT
    ) -> bool:
        """
        Acquire a slot for the model.
        
        Args:
            provider: Provider name
            model_id: Model ID
            timeout: Max wait time in seconds
            
        Returns:
            True if acquired, False if timeout
        """
        model_key = self._get_model_key(provider, model_id)
        
        self._ensure_semaphore(model_key)
        
        with self._lock:
            self._metrics[model_key].total_requests += 1
            self._metrics[model_key].queued += 1
        
        try:
            semaphore = self._semaphores[model_key]
            
            acquired = await asyncio.wait_for(
                semaphore.acquire(),
                timeout=timeout
            )
            
            with self._lock:
                self._metrics[model_key].queued -= 1
                self._metrics[model_key].active += 1
                self._metrics[model_key].total_acquired += 1
            
            return True
            
        except asyncio.TimeoutError:
            with self._lock:
                self._metrics[model_key].queued -= 1
                self._metrics[model_key].rejected += 1
            
            logger.warning(f"[ConcurrencyLimiter] Timeout for {model_key}")
            return False
    
    def release(self, provider: str, model_id: str):
        """
        Release a slot for the model.
        
        Args:
            provider: Provider name
            model_id: Model ID
        """
        model_key = self._get_model_key(provider, model_id)
        
        with self._lock:
            if model_key not in self._semaphores:
                logger.warning(f"[ConcurrencyLimiter] No semaphore for {model_key}")
                return
            
            semaphore = self._semaphores[model_key]
            metrics = self._metrics[model_key]
            
            if metrics.active > 0:
                metrics.active -= 1
                semaphore.release()
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all model metrics.
        
        Returns:
            Dict of model_key -> metrics
        """
        with self._lock:
            return {k: v.to_dict() for k, v in self._metrics.items()}
    
    def get_model_metrics(self, provider: str, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a specific model.
        
        Args:
            provider: Provider name
            model_id: Model ID
            
        Returns:
            Metrics dict or None
        """
        model_key = self._get_model_key(provider, model_id)
        with self._lock:
            if model_key in self._metrics:
                return self._metrics[model_key].to_dict()
        return None
    
    def update_limit(self, provider: str, model_id: str, new_limit: int):
        """
        Update concurrency limit for a model.
        
        Note: This creates a new semaphore. Existing requests are not affected.
        
        Args:
            provider: Provider name
            model_id: Model ID
            new_limit: New max concurrent
        """
        model_key = self._get_model_key(provider, model_id)
        
        with self._lock:
            self._limits[model_key] = new_limit
            
            try:
                self._semaphores[model_key] = asyncio.Semaphore(new_limit)
            except RuntimeError:
                pass
            
            if model_key in self._metrics:
                self._metrics[model_key].max_concurrent = new_limit
            else:
                self._metrics[model_key] = ModelMetrics(
                    model_key=model_key,
                    max_concurrent=new_limit
                )
            
            logger.info(f"[ConcurrencyLimiter] Updated {model_key} limit to {new_limit}")
    
    def get_limit(self, provider: str, model_id: str) -> int:
        """
        Get current limit for a model.
        
        Args:
            provider: Provider name
            model_id: Model ID
            
        Returns:
            Max concurrent limit
        """
        model_key = self._get_model_key(provider, model_id)
        return self._limits.get(model_key, DEFAULT_MAX_CONCURRENT)
    
    def reset_metrics(self, provider: str = None, model_id: str = None):
        """
        Reset metrics for a model or all models.
        
        Args:
            provider: Provider name (optional)
            model_id: Model ID (optional)
        """
        with self._lock:
            if provider and model_id:
                model_key = self._get_model_key(provider, model_id)
                if model_key in self._metrics:
                    self._metrics[model_key].rejected = 0
                    self._metrics[model_key].total_requests = 0
                    self._metrics[model_key].total_acquired = 0
            else:
                for metrics in self._metrics.values():
                    metrics.rejected = 0
                    metrics.total_requests = 0
                    metrics.total_acquired = 0
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall summary.
        
        Returns:
            Summary dict
        """
        with self._lock:
            total_active = sum(m.active for m in self._metrics.values())
            total_queued = sum(m.queued for m in self._metrics.values())
            total_rejected = sum(m.rejected for m in self._metrics.values())
            total_requests = sum(m.total_requests for m in self._metrics.values())
            
            return {
                "total_models": len(self._metrics),
                "total_active": total_active,
                "total_queued": total_queued,
                "total_rejected": total_rejected,
                "total_requests": total_requests,
                "models": {k: v.to_dict() for k, v in self._metrics.items()}
            }


class ConcurrencyContext:
    """Context manager for automatic acquire/release"""
    
    def __init__(self, limiter: ConcurrencyLimiter, provider: str, model_id: str, timeout: float = DEFAULT_TIMEOUT):
        self._limiter = limiter
        self._provider = provider
        self._model_id = model_id
        self._timeout = timeout
        self._acquired = False
    
    async def __aenter__(self) -> bool:
        self._acquired = await self._limiter.acquire(
            self._provider,
            self._model_id,
            self._timeout
        )
        return self._acquired
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._acquired:
            self._limiter.release(self._provider, self._model_id)
        return False


_limiter_instance: Optional[ConcurrencyLimiter] = None
_limiter_lock = threading.Lock()


def get_concurrency_limiter() -> ConcurrencyLimiter:
    """Get singleton ConcurrencyLimiter instance"""
    global _limiter_instance
    if _limiter_instance is None:
        with _limiter_lock:
            if _limiter_instance is None:
                _limiter_instance = ConcurrencyLimiter()
    return _limiter_instance
