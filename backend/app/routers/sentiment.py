"""
市场情绪路由 v4 - Phase 4
涨跌分布直方图 + 全市场个股透视（基于 Sina HQ）+ 快讯情感联动
日内上涨家数走势（15秒轮询）
"""
import logging
import time
from datetime import datetime
from fastapi import APIRouter, Query
from app.services.sentiment_engine import (
    get_histogram, query_stocks, is_spot_ready,
    get_last_news_time, trigger_spot_fetch, trigger_news_fetch,
    get_news_sentiment,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 日内上涨家数历史（每15秒追加一点，最多480个点=2小时轮询）────────
_INTRADAY_MAX_POINTS = 480
_INTRADAY_HISTORY = []    # [{time: 'HH:MM', advance: N}]
_INTRADAY_LAST_TS = 0    # 上次追加时间


def _append_intraday(advance: int):
    """每15秒被 scheduler 调用一次，追加一个数据点"""
    global _INTRADAY_HISTORY, _INTRADAY_LAST_TS
    now = time.time()
    if now - _INTRADAY_LAST_TS < 14:   # 防抖：至少间隔14秒
        return
    _INTRADAY_LAST_TS = now
    t = datetime.now().strftime("%H:%M")
    _INTRADAY_HISTORY.append({"time": t, "advance": advance})
    if len(_INTRADAY_HISTORY) > _INTRADAY_MAX_POINTS:
        _INTRADAY_HISTORY.pop(0)


@router.get("/market/sentiment")
async def market_sentiment():
    """A股市场情绪摘要（简化版）"""
    h = get_histogram()
    _append_intraday(h.get("advance", 0))   # 每次查询顺便追加数据点
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


@router.get("/market/sentiment/intraday")
async def sentiment_intraday():
    """
    A股全天上涨家数折线图数据
    每15秒追加一个点，最多保留2小时历史（480个点）
    返回: {intraday: [{time: 'HH:MM', advance: N}], timestamp: str}
    """
    h = get_histogram()
    _append_intraday(h.get("advance", 0))
    return {
        "intraday": list(_INTRADAY_HISTORY),
        "current": h.get("advance", 0),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/market/sentiment/histogram")
async def sentiment_histogram():
    """
    涨跌分布直方图（11桶，基于 Sina HQ 50只重点股）
    Phase 4: 附带最新快讯情感分析结果
    """
    h = get_histogram()
    ns = get_news_sentiment()
    return {
        **h,
        "news_sentiment": {
            "score":  ns.get("score", 0.0),
            "label":  ns.get("label", "中性"),
            "bullish_count": ns.get("bullish_count", 0),
            "bearish_count": ns.get("bearish_count", 0),
            "total_count":  ns.get("total_count", 0),
            "keywords":     ns.get("keywords", []),
            "timestamp":    ns.get("timestamp", ""),
        }
    }


@router.get("/market/sentiment/news")
async def news_sentiment():
    """
    Phase 4: 快讯情感分析结果
    当 force_refresh 抓取新资讯时，同步更新此数据
    """
    return get_news_sentiment()


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
