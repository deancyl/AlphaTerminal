"""
Sector Endpoints - Extracted from market.py

This module contains sector-related endpoints:
- GET /market/sectors - Sector list
- POST /market/sectors/refresh - Refresh sectors cache
"""

from fastapi import APIRouter
from app.utils.response import success_response, error_response, ErrorCode
from .dependencies import logger

router = APIRouter()


@router.get("/market/sectors")
async def market_sectors():
    """
    真实行业板块数据 - Task 1: 毫秒级响应
    所有 akshare 调用全部移到后台 Job，API 只读 _SECTORS_CACHE
    """
    try:
        from app.services.sectors_cache import get_sectors, _SECTORS_CACHE_TS
        sectors = get_sectors()
        import time
        cache_age = int(time.time() - _SECTORS_CACHE_TS) if _SECTORS_CACHE_TS else 0
        return success_response({"sectors": sectors, "cache_age_seconds": cache_age})
    except Exception as e:
        logger.error(f"[market_sectors] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取行业板块失败: {str(e)}")


@router.post("/market/sectors/refresh")
async def market_sectors_refresh():
    """
    强制刷新行业板块缓存（手动刷新接口）
    """
    try:
        from app.services.sectors_cache import refresh_sectors_cache
        sectors = await refresh_sectors_cache()
        import time
        from app.services.sectors_cache import _SECTORS_CACHE_TS
        cache_age = int(time.time() - _SECTORS_CACHE_TS) if _SECTORS_CACHE_TS else 0
        return success_response({"sectors": sectors, "cache_age_seconds": cache_age, "refreshed": True})
    except Exception as e:
        logger.error(f"[market_sectors_refresh] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"刷新行业板块失败: {str(e)}")
