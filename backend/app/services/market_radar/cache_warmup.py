"""
Market Radar Cache Warmup

Wave 5-38: Pre-warm cache on server startup for faster initial response.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


async def warmup_market_radar_cache(
    timeout: float = 30.0,
    background: bool = True
) -> dict:
    """
    Pre-warm market radar cache on server startup.
    
    This reduces initial request latency by pre-fetching data
    before the first user request.
    
    Args:
        timeout: Maximum time for warmup in seconds
        background: If True, run in background without blocking
        
    Returns:
        Dictionary with warmup status and timing
    """
    from app.services.market_radar import build_treemap_data, detect_anomalies
    from app.services.data_cache import get_cache
    
    start_time = datetime.now()
    results = {
        "started_at": start_time.isoformat(),
        "tasks": {},
        "success": True,
    }
    
    try:
        # Run warmup tasks in parallel
        tasks = [
            ("treemap_sector", build_treemap_data(level="sector", timeout=timeout / 2)),
            ("treemap_stock", build_treemap_data(level="stock", timeout=timeout / 2)),
            ("anomalies", detect_anomalies(anomaly_type=None, top_n=10, timeout=timeout / 2)),
        ]
        
        task_results = await asyncio.gather(
            *[t[1] for t in tasks],
            return_exceptions=True
        )
        
        # Process results and cache them
        cache = get_cache()
        
        for i, (task_name, _) in enumerate(tasks):
            result = task_results[i]
            
            if isinstance(result, Exception):
                results["tasks"][task_name] = {
                    "status": "error",
                    "error": str(result),
                }
                results["success"] = False
            else:
                # Cache the result
                if task_name == "treemap_sector":
                    cache.set("market_radar:treemap:sector", result, ttl=60)
                elif task_name == "treemap_stock":
                    cache.set("market_radar:treemap:stock", result, ttl=60)
                elif task_name == "anomalies":
                    cache.set("market_radar:anomalies:all", result, ttl=30)
                
                results["tasks"][task_name] = {
                    "status": "success",
                    "data_count": len(result.get("data", result.get("anomalies", []))),
                }
    
    except Exception as e:
        logger.error(f"[MarketRadar] Cache warmup failed: {e}", exc_info=True)
        results["success"] = False
        results["error"] = str(e)
    
    end_time = datetime.now()
    results["completed_at"] = end_time.isoformat()
    results["duration_ms"] = int((end_time - start_time).total_seconds() * 1000)
    
    logger.info(f"[MarketRadar] Cache warmup completed in {results['duration_ms']}ms")
    
    return results


async def schedule_cache_warmup():
    """
    Schedule periodic cache warmup.
    
    Should be called from the scheduler to refresh cache
    before it expires.
    """
    logger.info("[MarketRadar] Starting scheduled cache warmup")
    await warmup_market_radar_cache(timeout=30.0, background=False)


def start_background_warmup():
    """
    Start cache warmup in background on server startup.
    
    This is non-blocking and runs in the background.
    """
    async def _warmup():
        try:
            await warmup_market_radar_cache(timeout=30.0, background=True)
        except Exception as e:
            logger.error(f"[MarketRadar] Background warmup failed: {e}", exc_info=True)
    
    # Create background task
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_warmup())
        logger.info("[MarketRadar] Background cache warmup started")
    except RuntimeError:
        # No running loop, will warmup on first request
        logger.info("[MarketRadar] No event loop, deferring cache warmup")
