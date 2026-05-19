"""
Market Radar API Router

Provides endpoints for market heat visualization and anomaly detection.

P2-10: User-friendly error messages (no stack traces exposed)
"""

import logging
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Query, HTTPException, Path

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

# P2-10: User-friendly error messages
ERROR_MESSAGES = {
    "timeout": "数据加载超时，请稍后重试",
    "network": "网络连接异常，请检查网络设置",
    "data_source": "数据源暂时不可用，正在使用备用数据",
    "invalid_param": "参数错误，请检查输入",
    "unknown": "服务暂时不可用，请稍后重试",
}


def sanitize_error_message(error: Exception) -> str:
    """
    P2-10: Convert technical error to user-friendly message.
    
    Never expose stack traces or internal details to users.
    """
    error_str = str(error).lower()
    
    # Check for known error patterns
    if "timeout" in error_str or "timed out" in error_str:
        return ERROR_MESSAGES["timeout"]
    if "connection" in error_str or "network" in error_str:
        return ERROR_MESSAGES["network"]
    if "akshare" in error_str or "data source" in error_str:
        return ERROR_MESSAGES["data_source"]
    
    # Default: generic message
    return ERROR_MESSAGES["unknown"]


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
    
    P1-5: Includes data_source field with source name and type
    """
    cache = get_cache()
    cache_key = f"market_radar:treemap:{level}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        data = await build_treemap_data(level=level, timeout=15.0)
        
        if "error" in data:
            # P2-10: Return user-friendly timeout message
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"])
            )
        
        cache.set(cache_key, data, ttl=TREEMAP_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get treemap: {e}")
        # P2-10: Sanitize error message
        raise HTTPException(
            status_code=500,
            detail=sanitize_error_message(e)
        )


@router.get("/anomalies")
async def get_anomalies():
    """
    Get all detected market anomalies.
    
    Returns 5 types of anomalies:
    - volatility: Stocks with highest amplitude
    - capital_outflow: Stocks with strongest capital outflow
    - institution_research: Most researched by institutions
    - new_high: Stocks hitting 60-day high (P1-4: Fixed with real K-line data)
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
            # P2-10: Return user-friendly timeout message
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"])
            )
        
        cache.set(cache_key, data, ttl=ANOMALY_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get anomalies: {e}")
        # P2-10: Sanitize error message
        raise HTTPException(
            status_code=500,
            detail=sanitize_error_message(e)
        )


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
    - new_high: Stocks hitting 60-day high (P1-4: Fixed)
    - volume_surge: Largest trading volume
    """
    try:
        at = AnomalyType(anomaly_type)
    except ValueError:
        # P2-10: User-friendly invalid type message
        valid_types = [t.value for t in AnomalyType]
        raise HTTPException(
            status_code=400,
            detail=f"无效的异常类型: {anomaly_type}。支持的类型: {', '.join(valid_types)}"
        )
    
    cache = get_cache()
    cache_key = f"market_radar:anomalies:{anomaly_type}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        data = await detect_anomalies(anomaly_type=at, top_n=10, timeout=15.0)
        
        if "error" in data:
            # P2-10: Return user-friendly timeout message
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"])
            )
        
        cache.set(cache_key, data, ttl=ANOMALY_CACHE_TTL)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get anomaly {anomaly_type}: {e}")
        # P2-10: Sanitize error message
        raise HTTPException(
            status_code=500,
            detail=sanitize_error_message(e)
        )


@router.get("/temperature")
async def get_market_temperature():
    """
    Get market temperature score (0-100).
    
    Temperature calculation:
    - Base score: 50 (neutral)
    - Advance/Decline ratio: ±50 points max
    - Limit up/down ratio: ±25 points max
    
    Formula: score = 50 + (advance - decline) / total * 50 + (limit_up - limit_down) / total * 25
    
    Color zones:
    - 0-20: Blue (冰点) - Extremely cold
    - 20-40: Cyan (偏冷) - Cold
    - 40-60: Yellow (中性) - Neutral
    - 60-80: Orange (偏热) - Warm
    - 80-100: Red (过热) - Overheated
    """
    try:
        from app.services.sentiment_engine import get_histogram
        
        sentiment = get_histogram()
        
        advance = sentiment.get('advance', 0)
        decline = sentiment.get('decline', 0)
        limit_up = sentiment.get('limit_up', 0)
        limit_down = sentiment.get('limit_down', 0)
        total = advance + decline + sentiment.get('unchanged', 0)
        
        if total == 0:
            score = 50  # Default to neutral if no data
        else:
            # Calculate temperature score
            advance_ratio = (advance - decline) / total
            limit_ratio = (limit_up - limit_down) / total
            score = 50 + advance_ratio * 50 + limit_ratio * 25
            # Clamp to 0-100
            score = max(0, min(100, score))
        
        # Determine temperature label
        if score < 20:
            label = "冰点"
            color = "#3b82f6"  # Blue
        elif score < 40:
            label = "偏冷"
            color = "#06b6d4"  # Cyan
        elif score < 60:
            label = "中性"
            color = "#fbbf24"  # Yellow
        elif score < 80:
            label = "偏热"
            color = "#f97316"  # Orange
        else:
            label = "过热"
            color = "#ef4444"  # Red
        
        return {
            "score": round(score, 1),
            "label": label,
            "color": color,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "advance": advance,
            "decline": decline,
            "total": total,
            "timestamp": sentiment.get('timestamp', datetime.now().isoformat())
        }
        
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get temperature: {e}")
        # P2-10: Sanitize error message
        raise HTTPException(
            status_code=500,
            detail=sanitize_error_message(e)
        )
