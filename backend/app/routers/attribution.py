"""
Multi-Factor Attribution Sandbox API

Provides endpoints for:
- Listing available factors
- Running attribution analysis
- Real-time factor calculations
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field, field_validator

from app.utils.errors import success_response, error_response, ErrorCode
from app.middleware import require_api_key
from app.db.database import _get_conn
from app.services.attribution import (
    get_factor_registry,
    get_attribution_engine,
    FactorCategory,
)
from app.utils.error_decorator import handle_errors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attribution", tags=["attribution"])

_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="attribution_")


class SandboxRequest(BaseModel):
    """Request model for attribution sandbox"""
    symbols: List[str] = Field(..., min_length=1, max_length=50, description="股票代码列表")
    factors: List[str] = Field(..., min_length=1, max_length=20, description="因子ID列表")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(default=100000, ge=10000, le=1e9, description="初始资金")
    
    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        return [s.strip().lower() for s in v if s.strip()]
    
    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        from datetime import datetime as dt
        try:
            dt.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f'日期格式错误：{v}，应为 YYYY-MM-DD')
        return v


class RealtimeRequest(BaseModel):
    """Request model for real-time attribution"""
    symbol: str = Field(..., min_length=1, max_length=20, description="股票代码")
    factors: List[str] = Field(..., min_length=1, max_length=20, description="因子ID列表")
    lookback_days: int = Field(default=60, ge=20, le=252, description="回溯天数")


@router.get("/factors")
@handle_errors(module="attribution")
async def list_factors(
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """列出所有可用因子"""
    registry = get_factor_registry()
    
    cat_filter = None
    if category:
        try:
            cat_filter = FactorCategory(category.lower())
        except ValueError:
            pass
    
    factors = registry.list_factors(cat_filter)
    
    return success_response({
        "factors": [f.to_dict() for f in factors],
        "total": len(factors),
    })


@router.get("/factors/categories")
@handle_errors(module="attribution")
async def list_categories():
    """列出因子类别"""
    registry = get_factor_registry()
    categories = registry.list_categories()
    
    return success_response({
        "categories": categories,
        "total": len(categories),
    })


@router.post("/sandbox")
@handle_errors(module="attribution")
async def run_sandbox(req: SandboxRequest):
    """
    运行归因沙盒
    
    计算指定股票组合在选定因子上的归因分析
    """
    loop = asyncio.get_event_loop()
    
    def _sync_run():
        registry = get_factor_registry()
        engine = get_attribution_engine()
        
        all_results = []
        
        for symbol in req.symbols:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            
            conn = _get_conn()
            try:
                rows = conn.execute("""
                    SELECT date, open, high, low, close, volume
                    FROM market_data_daily
                    WHERE symbol = ? AND date >= ? AND date <= ?
                    ORDER BY date ASC
                """, (db_symbol, req.start_date, req.end_date)).fetchall()
                
                if len(rows) < 20:
                    continue
                
                df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                
                returns = np.zeros(len(df))
                returns[1:] = np.diff(np.log(df['close'].values + 1e-10))
                
                factor_data = pd.DataFrame(index=df.index)
                for factor_id in req.factors:
                    factor_values = registry.calculate(factor_id, df)
                    if factor_values is not None:
                        factor_data[factor_id] = factor_values
                
                result = engine.calculate_attribution(
                    returns=returns,
                    factor_data=factor_data,
                    factor_ids=req.factors,
                    period_start=req.start_date,
                    period_end=req.end_date,
                )
                
                all_results.append({
                    "symbol": symbol,
                    "attribution": result.to_dict(),
                })
                
            finally:
                conn.close()
        
        return all_results
    
    results = await loop.run_in_executor(_executor, _sync_run)
    
    if not results:
        return error_response(ErrorCode.NOT_FOUND, "未找到有效数据")
    
    return success_response({
        "results": results,
        "total": len(results),
        "request": {
            "symbols": req.symbols,
            "factors": req.factors,
            "start_date": req.start_date,
            "end_date": req.end_date,
        },
    })


@router.post("/sandbox/realtime")
@handle_errors(module="attribution")
async def run_realtime(req: RealtimeRequest):
    """
    实时归因计算
    
    基于最近N天的数据进行快速归因分析
    """
    loop = asyncio.get_event_loop()
    
    def _sync_run():
        registry = get_factor_registry()
        engine = get_attribution_engine()
        
        symbol = req.symbol.strip().lower()
        db_symbol = symbol.replace("sh", "").replace("sz", "")
        
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT date, open, high, low, close, volume
                FROM market_data_daily
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT ?
            """, (db_symbol, req.lookback_days + 10)).fetchall()
            
            if len(rows) < 20:
                return None
            
            rows.reverse()
            df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            
            returns = np.zeros(len(df))
            returns[1:] = np.diff(np.log(df['close'].values + 1e-10))
            
            factor_data = pd.DataFrame(index=df.index)
            for factor_id in req.factors:
                factor_values = registry.calculate(factor_id, df)
                if factor_values is not None:
                    factor_data[factor_id] = factor_values
            
            result = engine.calculate_attribution(
                returns=returns,
                factor_data=factor_data,
                factor_ids=req.factors,
                period_start=str(df['date'].iloc[0].date()),
                period_end=str(df['date'].iloc[-1].date()),
            )
            
            return {
                "symbol": symbol,
                "attribution": result.to_dict(),
                "latest_price": float(df['close'].iloc[-1]),
                "latest_date": str(df['date'].iloc[-1].date()),
            }
            
        finally:
            conn.close()
    
    result = await loop.run_in_executor(_executor, _sync_run)
    
    if result is None:
        return error_response(ErrorCode.NOT_FOUND, "未找到有效数据")
    
    return success_response(result)


@router.get("/health")
@handle_errors(module="attribution")
async def health_check():
    """健康检查"""
    registry = get_factor_registry()
    engine = get_attribution_engine()
    
    return success_response({
        "status": "healthy",
        "factors_registered": len(registry.list_factors()),
        "categories": len(registry.list_categories()),
    })
