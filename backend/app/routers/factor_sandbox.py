"""
Factor Sandbox API - Stock Screening with Factor Filters

Provides endpoints for:
- Listing all factors (attribution + screening)
- Screening stocks with factor filters
- Quick backtest preview for screened stocks
- SSE streaming for real-time screening progress
"""

import asyncio
import logging
import time
import threading
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sse_starlette.sse import EventSourceResponse

from app.utils.response import success_response, error_response, ErrorCode
from app.services.attribution import get_factor_registry, FactorCategory
from app.services.factor_sandbox.screener import (
    get_stock_screener,
    Universe,
    ScreeningFactor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/factor_sandbox", tags=["factor_sandbox"])

_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="factor_sandbox_")

# Progress tracking for SSE streaming
_screening_progress: Dict[str, Dict[str, Any]] = {}
_progress_lock = threading.Lock()

SENSITIVE_PATTERNS = [
    r'/[\w/.-]+\.py',
    r'line \d+',
    r'Traceback',
    r'File "',
    r'Error:',
    r'Exception:',
    r'localhost',
    r'127\.0\.0\.1',
    r'0\.0\.0\.0',
    r'password',
    r'secret',
    r'api[_-]?key',
    r'token',
]

def sanitize_error_message(error: Exception) -> str:
    import re
    msg = str(error)
    for pattern in SENSITIVE_PATTERNS:
        msg = re.sub(pattern, '[REDACTED]', msg, flags=re.IGNORECASE)
    if len(msg) > 100:
        msg = msg[:100] + '...'
    return msg

USER_FRIENDLY_ERRORS = {
    'ConnectionError': '网络连接失败，请检查网络设置',
    'TimeoutError': '请求超时，请稍后重试',
    'KeyError': '数据格式错误',
    'ValueError': '参数错误',
    'ImportError': '服务配置错误',
}

# Thread-safe cache for factor values with automatic cleanup
class ThreadSafeFactorCache:
    """
    Thread-safe factor value cache with automatic TTL cleanup.
    
    Features:
    - asyncio.Lock for async context protection
    - threading.Lock for sync context protection (used in executor)
    - Automatic cleanup of expired entries
    - Max entries limit to prevent memory bloat
    """
    
    def __init__(self, ttl: int = 300, max_entries: int = 10000):
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        self._ttl = ttl
        self._max_entries = max_entries
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value (sync, used in executor)"""
        with self._sync_lock:
            if key in self._cache:
                timestamp, value = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    return value
                else:
                    # Remove expired entry
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value (sync, used in executor)"""
        with self._sync_lock:
            # Cleanup if needed
            self._cleanup_if_needed()
            
            # Enforce max entries limit
            if len(self._cache) >= self._max_entries:
                self._cleanup_expired()
                if len(self._cache) >= self._max_entries:
                    # Remove oldest entries
                    oldest_keys = sorted(self._cache.keys(), 
                                         key=lambda k: self._cache[k][0])[:100]
                    for k in oldest_keys:
                        del self._cache[k]
            
            self._cache[key] = (time.time(), value)
    
    async def get_async(self, key: str) -> Optional[Any]:
        """Get cached value (async)"""
        async with self._async_lock:
            return self.get(key)
    
    async def set_async(self, key: str, value: Any) -> None:
        """Set cached value (async)"""
        async with self._async_lock:
            self.set(key, value)
    
    def _cleanup_if_needed(self) -> None:
        """Cleanup expired entries if interval elapsed"""
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = time.time()
    
    def _cleanup_expired(self) -> None:
        """Remove all expired entries"""
        now = time.time()
        expired_keys = [
            k for k, (ts, _) in self._cache.items()
            if now - ts >= self._ttl
        ]
        for k in expired_keys:
            del self._cache[k]
    
    def clear(self) -> None:
        """Clear all cached entries"""
        with self._sync_lock:
            self._cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._sync_lock:
            now = time.time()
            valid_entries = sum(
                1 for ts, _ in self._cache.values()
                if now - ts < self._ttl
            )
            return {
                "total_entries": len(self._cache),
                "valid_entries": valid_entries,
                "expired_entries": len(self._cache) - valid_entries,
                "ttl_seconds": self._ttl,
                "max_entries": self._max_entries,
            }

# Global thread-safe cache instance
_factor_cache = ThreadSafeFactorCache(ttl=300, max_entries=10000)


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class FactorParam(BaseModel):
    """Factor parameter configuration"""
    id: str = Field(..., description="Factor ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="Factor parameters")


class ScreenRequest(BaseModel):
    """Request model for stock screening"""
    factors: List[FactorParam] = Field(..., min_length=1, max_length=20, description="Factor filters")
    universe: str = Field(default="hs300", description="Stock universe: all, hs300, zz500, cyb50")
    limit: int = Field(default=50, ge=1, le=500, description="Max results to return")
    
    @field_validator('universe')
    @classmethod
    def validate_universe(cls, v: str) -> str:
        valid = ['all', 'hs300', 'zz500', 'cyb50']
        if v.lower() not in valid:
            raise ValueError(f'universe must be one of: {valid}')
        return v.lower()


class BacktestPreviewRequest(BaseModel):
    """Request model for quick backtest preview"""
    symbols: List[str] = Field(..., min_length=1, max_length=10, description="Stock symbols")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    initial_capital: float = Field(default=100000, ge=10000, le=1e9, description="Initial capital")
    
    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        return [s.strip().lower() for s in v if s.strip()]
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f'Invalid date format: {v}, expected YYYY-MM-DD')
        return v
    
    @model_validator(mode='after')
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError('start_date must be before end_date')
        return self


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    registry = get_factor_registry()
    screener = get_stock_screener()
    
    return success_response({
        "status": "healthy",
        "factors_registered": len(registry.list_factors()),
        "categories": len(registry.list_categories()),
        "universes": [u.value for u in Universe],
    })


@router.get("/factors")
async def list_factors(
    category: Optional[str] = Query(None, description="Filter by category"),
    screening_only: bool = Query(False, description="Only show screening factors"),
):
    """
    List all available factors
    
    Returns factors from both attribution and screening categories
    """
    registry = get_factor_registry()
    
    cat_filter = None
    if category:
        try:
            cat_filter = FactorCategory(category.lower())
        except ValueError:
            pass
    
    factors = registry.list_factors(cat_filter)
    
    # Filter for screening-only if requested
    if screening_only:
        screening_factor_ids = [
            "macd_golden_cross",
            "rsi_oversold", 
            "breakout_ma",
            "foreign_inflow",
            # TODO: Integrate with copilot API for real sentiment analysis
            # "llm_sentiment",
            "volume_surge",
            "institution_research",
            "new_high",
        ]
        factors = [f for f in factors if f.id in screening_factor_ids]
    
    return success_response({
        "factors": [f.to_dict() for f in factors],
        "total": len(factors),
    })


@router.get("/factors/screening")
async def list_screening_factors():
    """
    List screening-specific factors
    
    These factors are designed for stock screening with real-time data
    """
    registry = get_factor_registry()
    
    screening_factor_ids = [
        "macd_golden_cross",
        "rsi_oversold",
        "breakout_ma",
        "foreign_inflow",
        # TODO: Integrate with copilot API for real sentiment analysis
        # "llm_sentiment",
        "volume_surge",
        "institution_research",
        "new_high",
    ]
    
    factors = []
    for fid in screening_factor_ids:
        factor = registry.get_factor(fid)
        if factor:
            factors.append(factor)
    
    return success_response({
        "factors": [f.to_dict() for f in factors],
        "total": len(factors),
        "categories": [
            {"id": "technical", "name": "技术信号", "icon": "📊"},
            {"id": "sentiment", "name": "市场情绪", "icon": "🧠"},
            {"id": "fund_flow", "name": "资金流向", "icon": "💰"},
        ],
    })


@router.post("/screen")
async def screen_stocks(req: ScreenRequest):
    """
    Screen stocks with factor filters
    
    Returns stocks that match all factor criteria, sorted by composite score
    """
    start_time = time.time()
    
    try:
        # Run screening with timeout protection
        screener = get_stock_screener()
        
        # Convert request to screening factors
        screening_factors = []
        for fp in req.factors:
            screening_factors.append(ScreeningFactor(
                id=fp.id,
                params=fp.params,
            ))
        
        # Execute screening with 30s timeout
        result = await asyncio.wait_for(
            screener.screen_stocks(
                factors=screening_factors,
                universe=Universe(req.universe),
                limit=req.limit,
            ),
            timeout=30.0,
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return success_response({
            "stocks": result["stocks"],
            "total": result["total"],
            "execution_time_ms": execution_time_ms,
            "universe": req.universe,
            "factors_applied": len(req.factors),
        })
        
    except asyncio.TimeoutError:
        logger.error(f"[FactorSandbox] Screening timeout after 30s")
        return error_response(ErrorCode.TIMEOUT_ERROR, "筛选超时，请尝试减少因子数量或缩小股票范围")
    except Exception as e:
        logger.error(f"[FactorSandbox] Screening error: {e}", exc_info=True)
        error_type = type(e).__name__
        user_msg = USER_FRIENDLY_ERRORS.get(error_type, '筛选失败，请稍后重试')
        return error_response(ErrorCode.INTERNAL_ERROR, user_msg)


@router.post("/backtest_preview")
async def backtest_preview(req: BacktestPreviewRequest):
    """
    Quick backtest preview for screened stocks
    
    Runs a simple buy-and-hold backtest to show potential performance
    """
    loop = asyncio.get_event_loop()
    
    def _sync_backtest():
        from app.db.database import _get_conn
        
        results = []
        
        for symbol in req.symbols:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            
            conn = _get_conn()
            try:
                rows = conn.execute("""
                    SELECT date, close
                    FROM market_data_daily
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """, (db_symbol, req.start_date, req.end_date)).fetchall()
                
                if len(rows) < 10:
                    continue
                
                closes = np.array([r[1] for r in rows])
                
                # Simple buy-and-hold return
                start_price = closes[0]
                end_price = closes[-1]
                total_return = (end_price - start_price) / start_price * 100
                
                # Calculate max drawdown
                peak = closes[0]
                max_dd = 0
                for c in closes:
                    if c > peak:
                        peak = c
                    dd = (peak - c) / peak * 100
                    if dd > max_dd:
                        max_dd = dd
                
                # Calculate volatility (annualized)
                returns = np.diff(np.log(closes + 1e-10))
                volatility = np.std(returns) * np.sqrt(252) * 100
                
                results.append({
                    "symbol": symbol,
                    "start_price": float(start_price),
                    "end_price": float(end_price),
                    "total_return_pct": round(total_return, 2),
                    "max_drawdown_pct": round(max_dd, 2),
                    "volatility_pct": round(volatility, 2),
                    "trading_days": len(closes),
                })
                
            finally:
                conn.close()
        
        return results
    
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _sync_backtest),
            timeout=30.0,
        )
        
        if not results:
            return error_response(ErrorCode.NOT_FOUND, "No valid data found for specified stocks")
        
        # Sort by total return
        results.sort(key=lambda x: x["total_return_pct"], reverse=True)
        
        return success_response({
            "results": results,
            "total": len(results),
            "period": {
                "start_date": req.start_date,
                "end_date": req.end_date,
            },
            "initial_capital": req.initial_capital,
        })
        
    except asyncio.TimeoutError:
        logger.error(f"[FactorSandbox] Backtest preview timeout")
        return error_response(ErrorCode.TIMEOUT_ERROR, "回测预览超时，请稍后重试")
    except Exception as e:
        logger.error(f"[FactorSandbox] Backtest preview error: {e}", exc_info=True)
        error_type = type(e).__name__
        user_msg = USER_FRIENDLY_ERRORS.get(error_type, '回测预览失败，请稍后重试')
        return error_response(ErrorCode.INTERNAL_ERROR, user_msg)


@router.get("/cache/stats")
async def cache_stats():
    """Get factor cache statistics"""
    return success_response(_factor_cache.stats())


@router.post("/cache/clear")
async def clear_cache():
    """Clear factor cache"""
    _factor_cache.clear()
    return success_response({"message": "Cache cleared"})


# ─────────────────────────────────────────────────────────────────────────────
# SSE Streaming Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class ScreenStreamRequest(BaseModel):
    """Request model for streaming stock screening"""
    factors: List[FactorParam] = Field(..., min_length=1, max_length=20)
    universe: str = Field(default="hs300")
    limit: int = Field(default=50, ge=1, le=500)
    
    @field_validator('universe')
    @classmethod
    def validate_universe(cls, v: str) -> str:
        valid = ['all', 'hs300', 'zz500', 'cyb50']
        if v.lower() not in valid:
            raise ValueError(f'universe must be one of: {valid}')
        return v.lower()


def _update_progress(task_id: str, **kwargs):
    with _progress_lock:
        if task_id not in _screening_progress:
            _screening_progress[task_id] = {
                "status": "pending",
                "screened_stocks": 0,
                "total_stocks": 0,
                "matches": [],
                "error": None,
            }
        _screening_progress[task_id].update(kwargs)


def _get_progress(task_id: str) -> Optional[Dict[str, Any]]:
    with _progress_lock:
        return _screening_progress.get(task_id)


def _clear_progress(task_id: str):
    with _progress_lock:
        _screening_progress.pop(task_id, None)


@router.post("/screen/stream/start")
async def start_streaming_screen(req: ScreenStreamRequest):
    """
    Start a streaming screening task and return task_id for SSE connection.
    
    Use GET /screen/{task_id}/stream to receive progress updates.
    """
    task_id = str(uuid.uuid4())
    
    _update_progress(
        task_id,
        status="pending",
        screened_stocks=0,
        total_stocks=0,
        matches=[],
        error=None,
    )
    
    asyncio.create_task(_run_screening_task(
        task_id=task_id,
        factors=req.factors,
        universe=req.universe,
        limit=req.limit,
    ))
    
    return success_response({
        "task_id": task_id,
        "stream_url": f"/api/v1/factor_sandbox/screen/{task_id}/stream",
    })


async def _run_screening_task(
    task_id: str,
    factors: List[FactorParam],
    universe: str,
    limit: int,
):
    """Background task to run screening with progress updates"""
    try:
        screener = get_stock_screener()
        
        screening_factors = [
            ScreeningFactor(id=fp.id, params=fp.params)
            for fp in factors
        ]
        
        _update_progress(task_id, status="running")
        
        result = await screener.screen_stocks_with_progress(
            factors=screening_factors,
            universe=Universe(universe),
            limit=limit,
            progress_callback=lambda screened, total, matches: _update_progress(
                task_id,
                screened_stocks=screened,
                total_stocks=total,
                matches=matches[:limit],
            ),
        )
        
        _update_progress(
            task_id,
            status="complete",
            screened_stocks=result["progress"]["screened_stocks"],
            total_stocks=result["progress"]["total_stocks"],
            matches=result["stocks"][:limit],
        )
        
    except asyncio.CancelledError:
        _update_progress(task_id, status="cancelled", error="Task cancelled")
    except Exception as e:
        logger.error(f"[FactorSandbox] Streaming screening error: {e}", exc_info=True)
        error_type = type(e).__name__
        user_msg = USER_FRIENDLY_ERRORS.get(error_type, '筛选失败，请稍后重试')
        _update_progress(task_id, status="error", error=user_msg)


@router.get("/screen/{task_id}/stream")
async def stream_screening_progress(task_id: str):
    """
    SSE endpoint for real-time screening progress.
    
    Yields events with format:
    - type: "progress" | "complete" | "error"
    - data: progress info or results
    """
    async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
        last_screened = 0
        
        while True:
            progress = _get_progress(task_id)
            
            if progress is None:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Task not found"}),
                }
                break
            
            status = progress.get("status")
            
            if status == "pending":
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "type": "progress",
                        "status": "pending",
                        "screened_stocks": 0,
                        "total_stocks": 0,
                        "matches": [],
                    }),
                }
            elif status == "running":
                current_screened = progress.get("screened_stocks", 0)
                if current_screened != last_screened:
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "type": "progress",
                            "status": "running",
                            "screened_stocks": progress.get("screened_stocks", 0),
                            "total_stocks": progress.get("total_stocks", 0),
                            "matches": progress.get("matches", []),
                        }),
                    }
                    last_screened = current_screened
            elif status == "complete":
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "type": "complete",
                        "status": "complete",
                        "screened_stocks": progress.get("screened_stocks", 0),
                        "total_stocks": progress.get("total_stocks", 0),
                        "matches": progress.get("matches", []),
                    }),
                }
                _clear_progress(task_id)
                break
            elif status == "error":
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "type": "error",
                        "error": progress.get("error", "Unknown error"),
                    }),
                }
                _clear_progress(task_id)
                break
            elif status == "cancelled":
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "type": "cancelled",
                        "error": "Task cancelled",
                    }),
                }
                _clear_progress(task_id)
                break
            
            await asyncio.sleep(0.3)
    
    return EventSourceResponse(event_generator())


@router.post("/screen/{task_id}/cancel")
async def cancel_screening_task(task_id: str):
    """Cancel a running screening task"""
    progress = _get_progress(task_id)
    if progress is None:
        return error_response(ErrorCode.NOT_FOUND, "Task not found")
    
    if progress.get("status") in ["complete", "error", "cancelled"]:
        return error_response(ErrorCode.BAD_REQUEST, "Task already finished")
    
    _update_progress(task_id, status="cancelled", error="Cancelled by user")
    return success_response({"message": "Task cancelled"})
