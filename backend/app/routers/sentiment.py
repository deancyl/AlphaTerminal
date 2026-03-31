"""
市场情绪路由 v3 - Phase 3
涨跌分布直方图 + 全市场个股透视（基于 Sina HQ 50只重点股）
"""
import logging
from fastapi import APIRouter, Query
from app.services.sentiment_engine import (
    get_histogram, query_stocks, is_spot_ready,
    get_last_news_time, trigger_spot_fetch, trigger_news_fetch,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/market/sentiment")
async def market_sentiment():
    """A股市场情绪摘要（简化版）"""
    h = get_histogram()
    return {
        "advance":    h.get("advance", 0),
        "decline":    h.get("decline", 0),
        "unchanged":  h.get("unchanged", 0),
        "limit_up":   h.get("limit_up", 0),
        "limit_down": h.get("limit_down", 0),
        "total":      h.get("total", 0),
        "up_ratio":   h.get("up_ratio", 0.0),
        "timestamp":  h.get("timestamp", ""),
    }


@router.get("/market/sentiment/histogram")
async def sentiment_histogram():
    """涨跌分布直方图（11桶，基于 Sina HQ 50只重点股）"""
    return get_histogram()


@router.get("/market/stocks")
async def market_stocks(
    page:      int    = Query(1,      ge=1, description="页码"),
    page_size: int    = Query(20,     ge=1, le=100, description="每页条数"),
    sort_by:   str    = Query("chg_pct", description="排序字段：chg_pct|turnover|price|code"),
    asc:       bool   = Query(False,  description="升序（false=降序）"),
):
    """全市场个股透视看板（50只重点股票，基于 Sina HQ 实时行情）"""
    return query_stocks(page=page, page_size=page_size, sort_by=sort_by, asc=asc)


@router.get("/debug/scheduler")
async def debug_scheduler():
    """
    调度器心跳调试接口
    返回各后台任务的最后成功时间
    """
    return {
        "news_last_success":  get_last_news_time() or "从未成功",
        "spot_cache_ready":  is_spot_ready(),
    }


@router.post("/debug/trigger")
async def debug_trigger():
    """手动触发一次全量刷新（调试用）"""
    trigger_spot_fetch()
    trigger_news_fetch()
    return {"status": "triggered", "message": "已触发后台刷新，请稍后查看 /debug/scheduler"}
