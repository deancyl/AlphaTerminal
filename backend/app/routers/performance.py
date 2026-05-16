"""
Performance Analysis API Router
"""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter()

analyzer = PerformanceAnalyzer()


class TearsheetRequest(BaseModel):
    returns: List[float]
    dates: Optional[List[str]] = None
    benchmark_returns: Optional[List[float]] = None


class EquityCurveRequest(BaseModel):
    equity_curve: List[Dict[str, Any]]
    initial_capital: float


class TradesRequest(BaseModel):
    trades: List[Dict[str, Any]]
    initial_capital: float
    start_date: str
    end_date: str


@router.post("/tearsheet")
async def generate_tearsheet(req: TearsheetRequest):
    """Generate comprehensive performance tear sheet from returns"""
    if not req.returns:
        raise HTTPException(400, "returns list cannot be empty")
    
    # CPU 密集计算移入线程池，避免阻塞事件循环
    result = await asyncio.to_thread(
        analyzer.calculate_tearsheet_metrics,
        returns=req.returns,
        dates=req.dates,
        benchmark_returns=req.benchmark_returns
    )
    
    if result["code"] != 0:
        raise HTTPException(400, result.get("message", "Failed to calculate metrics"))
    
    return result


@router.post("/tearsheet/equity")
async def generate_tearsheet_from_equity(req: EquityCurveRequest):
    """Generate tear sheet from equity curve"""
    if not req.equity_curve:
        raise HTTPException(400, "equity_curve cannot be empty")
    
    if req.initial_capital <= 0:
        raise HTTPException(400, "initial_capital must be positive")
    
    # CPU 密集计算移入线程池
    result = await asyncio.to_thread(
        analyzer.calculate_from_equity_curve,
        equity_curve=req.equity_curve,
        initial_capital=req.initial_capital
    )
    
    if result["code"] != 0:
        raise HTTPException(400, result.get("message", "Failed to calculate metrics"))
    
    return result


@router.post("/tearsheet/trades")
async def generate_tearsheet_from_trades(req: TradesRequest):
    """Generate tear sheet from trade list"""
    if not req.trades:
        raise HTTPException(400, "trades cannot be empty")
    
    if req.initial_capital <= 0:
        raise HTTPException(400, "initial_capital must be positive")
    
    # CPU 密集计算移入线程池
    result = await asyncio.to_thread(
        analyzer.calculate_from_trades,
        trades=req.trades,
        initial_capital=req.initial_capital,
        start_date=req.start_date,
        end_date=req.end_date
    )
    
    if result["code"] != 0:
        raise HTTPException(400, result.get("message", "Failed to calculate metrics"))
    
    return result


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "performance_analyzer"}
