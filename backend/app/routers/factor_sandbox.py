"""
Factor Sandbox API - Stock Screening with Factor Filters

Provides endpoints for:
- Listing all factors (attribution + screening)
- Screening stocks with factor filters
- Quick backtest preview for screened stocks
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from app.utils.response import success_response, error_response, ErrorCode
from app.services.attribution import get_factor_registry, FactorCategory
from app.services.factor_sandbox.screener import (
    get_stock_screener,
    Universe,
    ScreeningFactor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/factor_sandbox", tags=["factor_sandbox"])

# Dedicated thread pool for CPU-bound factor calculations
_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="factor_sandbox_")

# Cache for factor values (5 minutes)
_factor_cache: Dict[str, tuple] = {}  # key: (symbol, factor_id), value: (timestamp, value)
_CACHE_TTL = 300  # 5 minutes


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
            "llm_sentiment",
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
        "llm_sentiment",
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
        return error_response(ErrorCode.TIMEOUT_ERROR, "Screening timeout, please try with fewer factors")
    except Exception as e:
        logger.error(f"[FactorSandbox] Screening error: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"Screening failed: {str(e)}")


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
        return error_response(ErrorCode.TIMEOUT_ERROR, "Backtest preview timeout")
    except Exception as e:
        logger.error(f"[FactorSandbox] Backtest preview error: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"Backtest preview failed: {str(e)}")


@router.get("/cache/stats")
async def cache_stats():
    """Get factor cache statistics"""
    return success_response({
        "cache_entries": len(_factor_cache),
        "cache_ttl_seconds": _CACHE_TTL,
    })


@router.post("/cache/clear")
async def clear_cache():
    """Clear factor cache"""
    global _factor_cache
    _factor_cache = {}
    return success_response({"message": "Cache cleared"})
