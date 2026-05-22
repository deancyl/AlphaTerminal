"""
Token Tracking Service

Per-request token tracking with cost calculation.

Key Features:
- Per-request token counting (prompt + completion)
- Cost calculation using pricing catalog
- Time-series storage
- Aggregation (hourly, daily, weekly)
- Background aggregation thread
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from threading import RLock

from app.db import token_usage_db
from app.db.seed_pricing_catalog import calculate_cost, get_pricing_by_model

logger = logging.getLogger(__name__)

AGGREGATION_INTERVAL_SECONDS = 300


@dataclass
class TokenUsageRecord:
    """Token usage record"""
    request_id: str
    model_id: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "provider": self.provider,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at
        }


class TokenTrackingService:
    """
    Token usage tracking with cost calculation.
    
    Features:
    - Track per-request token usage
    - Calculate cost using pricing catalog
    - Aggregate usage statistics
    """
    
    def __init__(self):
        self._lock = RLock()
        self._aggregation_thread: Optional[threading.Thread] = None
        self._shutdown = False
        
        self._start_aggregation_thread()
        logger.info("[TokenTrackingService] Initialized")
    
    def _start_aggregation_thread(self):
        """Start background aggregation thread"""
        self._aggregation_thread = threading.Thread(
            target=self._aggregation_loop,
            daemon=True,
            name="TokenAggregation"
        )
        self._aggregation_thread.start()
    
    def _aggregation_loop(self):
        """Background aggregation loop"""
        while not self._shutdown:
            try:
                time.sleep(AGGREGATION_INTERVAL_SECONDS)
                self._run_aggregation()
            except Exception as e:
                logger.error(f"[TokenTracking] Aggregation error: {e}", exc_info=True)
    
    def _run_aggregation(self):
        """Run aggregation for hourly/daily stats"""
        try:
            now = datetime.now()
            
            hourly_key = now.strftime("%Y-%m-%d-%H")
            daily_key = now.strftime("%Y-%m-%d")
            
            hourly_stats = token_usage_db.get_daily_totals(now.strftime("%Y-%m-%d"))
            
            if hourly_stats["request_count"] > 0:
                token_usage_db.save_usage_aggregate(
                    aggregate_type="hourly",
                    aggregate_key=hourly_key,
                    total_requests=hourly_stats["request_count"],
                    total_prompt_tokens=hourly_stats["total_prompt_tokens"],
                    total_completion_tokens=hourly_stats["total_completion_tokens"],
                    total_cost_usd=hourly_stats["total_cost_usd"]
                )
            
            logger.debug(f"[TokenTracking] Aggregated: {hourly_key}")
            
        except Exception as e:
            logger.error(f"[TokenTracking] Aggregation failed: {e}", exc_info=True)
    
    def track_usage(
        self,
        model_id: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TokenUsageRecord:
        """
        Track token usage for a request.
        
        Args:
            model_id: Model ID
            provider: Provider name
            prompt_tokens: Prompt token count
            completion_tokens: Completion token count
            session_id: Optional session ID
            user_id: Optional user ID
            duration_ms: Optional request duration
            metadata: Optional metadata
            
        Returns:
            TokenUsageRecord
        """
        total_tokens = prompt_tokens + completion_tokens
        
        cost = calculate_cost(model_id, prompt_tokens, completion_tokens)
        if cost is None:
            cost = self._estimate_cost(model_id, prompt_tokens, completion_tokens)
        
        request_id = token_usage_db.log_token_usage(
            model_id=model_id,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            session_id=session_id,
            user_id=user_id,
            duration_ms=duration_ms,
            metadata=metadata
        )
        
        return TokenUsageRecord(
            request_id=request_id,
            model_id=model_id,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            session_id=session_id,
            user_id=user_id,
            duration_ms=duration_ms,
            created_at=datetime.now().isoformat()
        )
    
    def _estimate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost if pricing not in catalog"""
        default_rates = {
            "gpt-4": (3e-5, 6e-5),
            "gpt-3.5": (5e-7, 1.5e-6),
            "claude": (3e-6, 1.5e-5),
            "deepseek": (1e-7, 2e-7),
            "qwen": (8e-7, 2e-6),
        }
        
        for prefix, (in_rate, out_rate) in default_rates.items():
            if model_id.startswith(prefix) or prefix in model_id.lower():
                return prompt_tokens * in_rate + completion_tokens * out_rate
        
        return 0.0
    
    def get_usage_history(
        self,
        model_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get usage history with filters.
        
        Args:
            model_id: Filter by model
            session_id: Filter by session
            user_id: Filter by user
            start_date: Start date filter
            end_date: End date filter
            limit: Max results
            
        Returns:
            List of usage records
        """
        if session_id:
            return token_usage_db.get_usage_by_session(session_id)
        elif user_id:
            return token_usage_db.get_usage_by_user(user_id, limit)
        elif model_id:
            return token_usage_db.get_usage_by_model(model_id, limit)
        elif start_date and end_date:
            return token_usage_db.get_usage_by_date_range(start_date, end_date, limit)
        else:
            return token_usage_db.get_usage_by_date_range(
                (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
                limit
            )
    
    def get_aggregated_stats(
        self,
        aggregate_type: str = "daily",
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated statistics.
        
        Args:
            aggregate_type: 'hourly', 'daily', 'weekly'
            limit: Max results
            
        Returns:
            List of aggregated stats
        """
        return token_usage_db.get_aggregates_by_type(aggregate_type, limit)
    
    def get_total_stats(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get total usage statistics.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            Total stats dict
        """
        if not start_time:
            start_time = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_time:
            end_time = datetime.now().strftime("%Y-%m-%d")
        
        trend = token_usage_db.get_usage_trend(days=30)
        
        total_requests = sum(t.get("request_count", 0) for t in trend)
        total_tokens = sum(t.get("total_tokens", 0) for t in trend)
        total_cost = sum(t.get("total_cost_usd", 0) for t in trend)
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost,
            "daily_trend": trend
        }
    
    def get_model_breakdown(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get usage breakdown by model.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            List of model stats
        """
        return token_usage_db.get_model_totals(days=30)
    
    def get_provider_breakdown(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get usage breakdown by provider.
        
        Args:
            days: Number of days
            
        Returns:
            List of provider stats
        """
        return token_usage_db.get_provider_totals(days=days)
    
    def get_pricing_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pricing info for a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            Pricing info or None
        """
        return get_pricing_by_model(model_id)
    
    def estimate_cost(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        Estimate cost for a request.
        
        Args:
            model_id: Model ID
            prompt_tokens: Prompt tokens
            completion_tokens: Completion tokens
            
        Returns:
            Estimated cost in USD
        """
        cost = calculate_cost(model_id, prompt_tokens, completion_tokens)
        if cost is not None:
            return cost
        return self._estimate_cost(model_id, prompt_tokens, completion_tokens)
    
    def shutdown(self):
        """Shutdown aggregation thread"""
        self._shutdown = True


_tracking_instance: Optional[TokenTrackingService] = None
_tracking_lock = threading.Lock()


def get_token_tracking_service() -> TokenTrackingService:
    """Get singleton TokenTrackingService instance"""
    global _tracking_instance
    if _tracking_instance is None:
        with _tracking_lock:
            if _tracking_instance is None:
                _tracking_instance = TokenTrackingService()
    return _tracking_instance
