"""
Market Radar API Router

Provides endpoints for market heat visualization and anomaly detection.
"""

import logging
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Query, HTTPException, Path, Path

from app.services.market_radar import (
    build_treemap_data,
    detect_anomalies,
    AnomalyType,
)
from app.services.data_cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market_radar", tags=["market_radar"])

TREEMAP_CACHE_TTL = 60
ANOMALY_CACHE_TTL = 30


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "market_radar",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/treemap")
async def get_treemap(
    level: Literal["sector", "stock"] = Query(
        default="sector",
        description="Treemap level: 'sector' for sector aggregation, 'stock' for individual stocks"
    )
):
    """
    Get treemap data for market heat visualization.
    
    Returns ECharts treemap format data with:
    - Sector level: Aggregated by industry with children stocks
    - Stock level: Individual stocks sorted by market cap
    """
    cache = get_cache()
    cache_key = f"market_radar:treemap:{level}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        data = await build_treemap_data(level=level, timeout=15.0)
        
        if "error" in data:
            raise HTTPException(status_code=504, detail="Treemap data fetch timeout")
        
        cache.set(cache_key, data, ttl=TREEMAP_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get treemap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies")
async def get_anomalies():
    """
    Get all detected market anomalies.
    
    Returns 5 types of anomalies:
    - volatility: Stocks with highest amplitude
    - capital_outflow: Stocks with strongest capital outflow
    - institution_research: Most researched by institutions
    - new_high: Stocks with highest gains
    - volume_surge: Stocks with largest trading volume
    """
    cache = get_cache()
    cache_key = "market_radar:anomalies:all"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        data = await detect_anomalies(anomaly_type=None, top_n=10, timeout=15.0)
        
        if "error" in data:
            raise HTTPException(status_code=504, detail="Anomaly detection timeout")
        
        cache.set(cache_key, data, ttl=ANOMALY_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies/{anomaly_type}")
async def get_anomaly_by_type(
    anomaly_type: str = Path(
        ...,
        description="Anomaly type: volatility, capital_outflow, institution_research, new_high, volume_surge"
    )
):
    """
    Get specific type of market anomaly.
    
    Supported types:
    - volatility: Highest amplitude stocks
    - capital_outflow: Strongest capital outflow
    - institution_research: Most researched by institutions
    - new_high: Stocks with highest gains
    - volume_surge: Largest trading volume
    """
    try:
        at = AnomalyType(anomaly_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid anomaly type: {anomaly_type}. "
                   f"Valid types: {[t.value for t in AnomalyType]}"
        )
    
    cache = get_cache()
    cache_key = f"market_radar:anomalies:{anomaly_type}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        data = await detect_anomalies(anomaly_type=at, top_n=10, timeout=15.0)
        
        if "error" in data:
            raise HTTPException(status_code=504, detail="Anomaly detection timeout")
        
        cache.set(cache_key, data, ttl=ANOMALY_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get anomaly {anomaly_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
