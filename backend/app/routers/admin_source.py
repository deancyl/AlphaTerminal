"""
数据源管理接口 - Phase 2
提供数据源状态查询、切换、健康检查等管理功能
"""
import logging
import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List, Dict
from app.services.fetcher_factory import FetcherFactory, get_market_fetcher

logger = logging.getLogger(__name__)
router = APIRouter()


# ── API 响应模型 ────────────────────────────────────────────────────────
class FetcherInfo(BaseModel):
    name: str
    display_name: str
    supported_features: List[str]


class SourceStatus(BaseModel):
    current: str
    available: List[str]
    proxy: Optional[str]


class HealthStatus(BaseModel):
    name: str
    healthy: bool
    latency_ms: Optional[float]


# ── 路由 ────────────────────────────────────────────────────────────────

@router.get("/api/v1/admin/data-sources")
async def list_data_sources():
    """列出所有可用的数据源"""
    try:
        fetchers = FetcherFactory.list_fetchers()
        current = FetcherFactory.get_current_name()
        proxy = FetcherFactory.get_proxy()
        
        fetcher_list = []
        for name in fetchers:
            info = FetcherFactory.get_fetcher_info(name)
            if info:
                fetcher_list.append(info)
        
        return {
            "code": 0,
            "message": "success",
            "data": {
                "sources": fetcher_list,
                "current": current,
                "proxy": proxy,
            }
        }
    except Exception as e:
        logger.error(f"list_data_sources error: {e}")
        return {"code": 500, "message": str(e)}


@router.post("/api/v1/admin/data-sources/switch")
async def switch_data_source(name: str):
    """切换当前数据源"""
    try:
        success = FetcherFactory.set_current(name)
        if success:
            return {
                "code": 0,
                "message": f"已切换到 {name}",
                "data": {"current": name}
            }
        else:
            return {
                "code": 404,
                "message": f"数据源 {name} 不存在",
            }
    except Exception as e:
        logger.error(f"switch_data_source error: {e}")
        return {"code": 500, "message": str(e)}


@router.post("/api/v1/admin/data-sources/health-check")
async def health_check_source(name: Optional[str] = None):
    """健康检查指定数据源或当前数据源"""
    try:
        target = name or FetcherFactory.get_current_name()
        fetcher = FetcherFactory.get_fetcher(target)
        
        if not fetcher:
            return {"code": 404, "message": f"数据源 {target} 不存在"}
        
        # 测试抓取上证指数
        start = time.time()
        healthy = await fetcher.ping()
        latency = (time.time() - start) * 1000 if healthy else None
        
        return {
            "code": 0,
            "message": "success",
            "data": {
                "name": target,
                "healthy": healthy,
                "latency_ms": round(latency, 2) if latency else None,
            }
        }
    except Exception as e:
        logger.error(f"health_check_source error: {e}")
        return {"code": 500, "message": str(e)}


@router.get("/api/v1/admin/data-sources/status")
async def get_source_status():
    """获取数据源整体状态"""
    try:
        current = FetcherFactory.get_current_name()
        proxy = FetcherFactory.get_proxy()
        available = FetcherFactory.list_fetchers()
        
        return {
            "code": 0,
            "message": "success",
            "data": {
                "current": current,
                "available": available,
                "proxy": proxy,
            }
        }
    except Exception as e:
        logger.error(f"get_source_status error: {e}")
        return {"code": 500, "message": str(e)}