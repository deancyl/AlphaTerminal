"""
Market Radar API Router

Provides endpoints for market heat visualization and anomaly detection.

P2-10: User-friendly error messages (no stack traces exposed)
"""

import logging
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Query, HTTPException, Path

from app.services.market_radar import (
    build_treemap_data,
    detect_anomalies,
    AnomalyType,
)
from app.services.market_radar.treemap_builder import (
    get_circuit_breaker as get_treemap_cb,
)
from app.services.market_radar.anomaly_detector import (
    get_circuit_breaker as get_anomaly_cb,
)
from app.services.data_cache import get_cache
from app.utils.error_decorator import handle_errors
from app.utils.errors import success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market_radar", tags=["market_radar"])

TREEMAP_CACHE_TTL = 60
ANOMALY_CACHE_TTL = 30
TREEMAP_TIMEOUT = 60.0

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
@handle_errors(module="market_radar")
async def health_check():
    treemap_cb = get_treemap_cb()
    anomaly_cb = get_anomaly_cb()

    treemap_stats = treemap_cb.get_stats()
    anomaly_stats = anomaly_cb.get_stats()

    return {
        "status": "ok",
        "service": "market_radar",
        "timestamp": datetime.now().isoformat(),
        "circuit_breakers": {
            "treemap": {
                "name": treemap_stats["name"],
                "state": treemap_stats["state"],
                "failure_count": treemap_stats["consecutive_failures"],
                "last_failure_time": treemap_stats["last_failure_time"],
            },
            "anomaly": {
                "name": anomaly_stats["name"],
                "state": anomaly_stats["state"],
                "failure_count": anomaly_stats["consecutive_failures"],
                "last_failure_time": anomaly_stats["last_failure_time"],
            },
        },
    }


@router.get("/treemap")
@handle_errors(module="market_radar")
async def get_treemap(
    level: Literal["sector", "stock"] = Query(
        default="sector",
        description="Treemap level: 'sector' for sector aggregation, 'stock' for individual stocks",
    )
):
    cache = get_cache()
    cache_key = f"market_radar:treemap:{level}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        data = await build_treemap_data(level=level, timeout=TREEMAP_TIMEOUT)

        if "error" in data:
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"]),
            )

        treemap_cb = get_treemap_cb()
        treemap_stats = treemap_cb.get_stats()
        data["circuit_breaker"] = {
            "state": treemap_stats["state"],
            "failure_count": treemap_stats["consecutive_failures"],
        }

        result = success_response(data)
        cache.set(cache_key, result, ttl=TREEMAP_CACHE_TTL)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get treemap: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error_message(e))


@router.get("/anomalies")
@handle_errors(module="market_radar")
async def get_anomalies():
    cache = get_cache()
    cache_key = "market_radar:anomalies:all"

    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        data = await detect_anomalies(
            anomaly_type=None, top_n=10, timeout=60.0
        )  # P0: Increased from 15s to 60s

        if "error" in data:
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"]),
            )

        anomaly_cb = get_anomaly_cb()
        anomaly_stats = anomaly_cb.get_stats()
        data["circuit_breaker"] = {
            "state": anomaly_stats["state"],
            "failure_count": anomaly_stats["consecutive_failures"],
        }

        result = success_response(data)
        cache.set(cache_key, result, ttl=ANOMALY_CACHE_TTL)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get anomalies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error_message(e))


@router.get("/anomalies/{anomaly_type}")
@handle_errors(module="market_radar")
async def get_anomaly_by_type(
    anomaly_type: str = Path(
        ...,
        description="Anomaly type: volatility, capital_outflow, institution_research, new_high, volume_surge",
    )
):
    try:
        at = AnomalyType(anomaly_type)
    except ValueError:
        valid_types = [t.value for t in AnomalyType]
        raise HTTPException(
            status_code=400,
            detail=f"无效的异常类型: {anomaly_type}。支持的类型: {', '.join(valid_types)}",
        )

    cache = get_cache()
    cache_key = f"market_radar:anomalies:{anomaly_type}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        data = await detect_anomalies(anomaly_type=at, top_n=10, timeout=15.0)

        if "error" in data:
            raise HTTPException(
                status_code=504,
                detail=ERROR_MESSAGES.get(data["error"], ERROR_MESSAGES["timeout"]),
            )

        anomaly_cb = get_anomaly_cb()
        anomaly_stats = anomaly_cb.get_stats()
        data["circuit_breaker"] = {
            "state": anomaly_stats["state"],
            "failure_count": anomaly_stats["consecutive_failures"],
        }

        result = success_response(data)
        cache.set(cache_key, result, ttl=ANOMALY_CACHE_TTL)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[MarketRadar] Failed to get anomaly {anomaly_type}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=sanitize_error_message(e))


@router.get("/temperature")
@handle_errors(module="market_radar")
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

        advance = sentiment.get("advance", 0)
        decline = sentiment.get("decline", 0)
        limit_up = sentiment.get("limit_up", 0)
        limit_down = sentiment.get("limit_down", 0)
        total = advance + decline + sentiment.get("unchanged", 0)

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
            "timestamp": sentiment.get("timestamp", datetime.now().isoformat()),
        }

    except Exception as e:
        logger.error(f"[MarketRadar] Failed to get temperature: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=sanitize_error_message(e))


@router.post("/circuit_breaker/reset")
async def reset_circuit_breaker():
    treemap_cb = get_treemap_cb()
    anomaly_cb = get_anomaly_cb()

    treemap_cb.reset()
    anomaly_cb.reset()

    treemap_stats = treemap_cb.get_stats()
    anomaly_stats = anomaly_cb.get_stats()

    return success_response(
        {
            "message": "CircuitBreakers reset successfully",
            "treemap": {"state": treemap_stats["state"]},
            "anomaly": {"state": anomaly_stats["state"]},
        }
    )


async def warmup_market_radar_cache():
    """Pre-populate market_radar cache on server startup."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    logger.info("[MarketRadar] Starting cache warmup...")

    warmup_executor = ThreadPoolExecutor(
        max_workers=5, thread_name_prefix="market_radar_warmup_"
    )
    loop = asyncio.get_running_loop()

    async def warmup_treemap():
        try:
            logger.info("[MarketRadar] Warming up treemap cache...")
            data = await build_treemap_data(level="sector", timeout=60.0)

            if "error" not in data:
                treemap_cb = get_treemap_cb()
                treemap_stats = treemap_cb.get_stats()
                data["circuit_breaker"] = {
                    "state": treemap_stats["state"],
                    "failure_count": treemap_stats["consecutive_failures"],
                }
                result = success_response(data)
                cache = get_cache()
                cache.set("market_radar:treemap:sector", result, ttl=TREEMAP_CACHE_TTL)
                logger.info("[MarketRadar] Treemap cache warmed up")
            else:
                logger.warning(
                    f"[MarketRadar] Treemap warmup returned error: {data.get('error')}"
                )
        except Exception as e:
            logger.warning(
                f"[MarketRadar] Failed to warmup treemap: {e}", exc_info=True
            )

    async def warmup_anomalies():
        try:
            logger.info("[MarketRadar] Warming up anomalies cache...")
            data = await detect_anomalies(anomaly_type=None, top_n=10, timeout=60.0)

            if "error" not in data:
                anomaly_cb = get_anomaly_cb()
                anomaly_stats = anomaly_cb.get_stats()
                data["circuit_breaker"] = {
                    "state": anomaly_stats["state"],
                    "failure_count": anomaly_stats["consecutive_failures"],
                }
                result = success_response(data)
                cache = get_cache()
                cache.set("market_radar:anomalies:all", result, ttl=ANOMALY_CACHE_TTL)
                logger.info("[MarketRadar] Anomalies cache warmed up")
            else:
                logger.warning(
                    f"[MarketRadar] Anomalies warmup returned error: {data.get('error')}"
                )
        except Exception as e:
            logger.warning(
                f"[MarketRadar] Failed to warmup anomalies: {e}", exc_info=True
            )

    async def warmup_temperature():
        try:
            logger.info("[MarketRadar] Warming up temperature cache...")
            from app.services.market_radar.treemap_builder import (
                _calculate_temperature_sync,
            )

            temp_data = await loop.run_in_executor(
                warmup_executor, _calculate_temperature_sync
            )
            cache = get_cache()
            cache.set("market_radar:temperature", temp_data, ttl=TREEMAP_CACHE_TTL)
            logger.info("[MarketRadar] Temperature cache warmed up")
        except Exception as e:
            logger.warning(f"[MarketRadar] Failed to warmup temperature: {e}")

    await asyncio.gather(
        warmup_treemap(),
        warmup_anomalies(),
        warmup_temperature(),
        return_exceptions=True,
    )

    warmup_executor.shutdown(wait=False)
    logger.info("[MarketRadar] Cache warmup complete")
