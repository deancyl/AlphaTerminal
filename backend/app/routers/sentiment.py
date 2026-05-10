"""
市场情绪路由 v4 - Phase 4
涨跌分布直方图 + 全市场个股透视（基于 Sina HQ）+ 快讯情感联动
日内上涨家数走势（15秒轮询）

Phase B: 统一 API 响应格式
- 所有响应使用标准格式: {code, message, data, timestamp}
- code: 0 表示成功，非 0 表示错误
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
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 日内多空历史（每15秒追加一点，最多480个点=2小时轮询）────────
_INTRADAY_MAX_POINTS = 480
_INTRADAY_HISTORY = []    # [{time: 'HH:MM', advance: N, decline: N}]
_INTRADAY_LAST_TS = 0    # 上次追加时间


def _append_intraday(advance: int, decline: int):
    """每15秒被 scheduler 调用一次，追加一个多空数据点"""
    global _INTRADAY_HISTORY, _INTRADAY_LAST_TS
    now = time.time()
    if now - _INTRADAY_LAST_TS < 14:   # 防抖：至少间隔14秒
        return
    _INTRADAY_LAST_TS = now
    t = datetime.now().strftime("%H:%M")
    _INTRADAY_HISTORY.append({"time": t, "advance": advance, "decline": decline})
    if len(_INTRADAY_HISTORY) > _INTRADAY_MAX_POINTS:
        _INTRADAY_HISTORY.pop(0)


@router.get("/market/sentiment")
async def market_sentiment():
    """A股市场情绪摘要（简化版）"""
    try:
        h = get_histogram()
        _append_intraday(h.get("advance", 0), h.get("decline", 0))
        return success_response({
            "advance":    h.get("advance", 0),
            "decline":    h.get("decline", 0),
            "unchanged":  h.get("unchanged", 0),
            "limit_up":   h.get("limit_up", 0),
            "limit_down": h.get("limit_down", 0),
            "total":      h.get("total", 0),
            "up_ratio":   h.get("up_ratio", 0.0),
            "advance_rate": h.get("up_ratio", 0.0),
            "timestamp":  h.get("timestamp", ""),
        })
    except Exception as e:
        logger.error(f"[market_sentiment] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取市场情绪失败: {str(e)}")


@router.get("/market/sentiment/intraday")
async def sentiment_intraday():
    """
    A股全天上涨家数折线图数据
    每15秒追加一个点，最多保留2小时历史（480个点）
    返回: {intraday: [{time: 'HH:MM', advance: N, decline: N}], timestamp: str}
    """
    try:
        h = get_histogram()
        _append_intraday(h.get("advance", 0), h.get("decline", 0))
        return success_response({
            "intraday": list(_INTRADAY_HISTORY),
            "advance": h.get("advance", 0),
            "decline": h.get("decline", 0),
        })
    except Exception as e:
        logger.error(f"[sentiment_intraday] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取日内数据失败: {str(e)}")


@router.get("/market/sentiment/histogram")
async def sentiment_histogram():
    """
    涨跌分布直方图（11桶，基于 Sina HQ 50只重点股）
    Phase 4: 附带最新快讯情感分析结果
    """
    try:
        h = get_histogram()
        ns = get_news_sentiment()
        return success_response({
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
        })
    except Exception as e:
        logger.error(f"[sentiment_histogram] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取直方图数据失败: {str(e)}")


@router.get("/market/sentiment/news")
async def news_sentiment():
    """
    Phase 4: 快讯情感分析结果
    当 force_refresh 抓取新资讯时，同步更新此数据
    """
    try:
        return success_response(get_news_sentiment())
    except Exception as e:
        logger.error(f"[news_sentiment] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取快讯情感失败: {str(e)}")


@router.get("/market/stocks")
async def market_stocks(
    page:      int    = Query(1,      ge=1, description="页码"),
    page_size: int    = Query(20,     ge=1, le=100, description="每页条数"),
    sort_by:   str    = Query("chg_pct", description="排序字段：chg_pct|turnover|price|code"),
    asc:       bool   = Query(False,  description="升序（false=降序）"),
):
    """全市场个股透视看板（50只重点股票，基于 Sina HQ 实时行情）"""
    try:
        return success_response(query_stocks(page=page, page_size=page_size, sort_by=sort_by, asc=asc))
    except Exception as e:
        logger.error(f"[market_stocks] 错误: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取个股列表失败: {str(e)}")


@router.get("/debug/scheduler")
async def debug_scheduler():
    """
    调度器心跳调试接口
    返回各后台任务的最后成功时间
    """
    return success_response({
        "news_last_success":  get_last_news_time() or "从未成功",
        "spot_cache_ready":  is_spot_ready(),
    })


@router.post("/debug/trigger")
async def debug_trigger():
    """手动触发一次全量刷新（调试用）"""
    trigger_spot_fetch()
    trigger_news_fetch()
    return success_response({"status": "triggered", "message": "已触发后台刷新，请稍后查看 /debug/scheduler"})

# ═══════════════════════════════════════════════════════════════
# 资金流向数据
# ═══════════════════════════════════════════════════════════════

@router.get("/market/fund_flow")
async def market_fund_flow():
    """市场资金流向 - 超大单/大单/中单/小单"""
    import akshare as ak
    
    try:
        df = ak.stock_market_fund_flow()
        # 获取最近30天数据
        df = df.tail(30)
        
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("日期", "")),
                "sh_close": float(row.get("上证-收盘价", 0) or 0),
                "sh_chg": float(row.get("上证-涨跌幅", 0) or 0),
                "sz_close": float(row.get("深证-收盘价", 0) or 0),
                "sz_chg": float(row.get("深证-涨跌幅", 0) or 0),
                "main_net": int(row.get("主力净流入-净额", 0) or 0),
                "main_pct": float(row.get("主力净流入-净占比", 0) or 0),
                "large_net": int(row.get("大单净流入-净额", 0) or 0),
                "large_pct": float(row.get("大单净流入-净占比", 0) or 0),
                "medium_net": int(row.get("中单净流入-净额", 0) or 0),
                "medium_pct": float(row.get("中单净流入-净占比", 0) or 0),
                "small_net": int(row.get("小单净流入-净额", 0) or 0),
                "small_pct": float(row.get("小单净流入-净占比", 0) or 0),
            })
        
        return success_response({
            "items": result,
            "total": len(result),
            "source": "akshare - stock_market_fund_flow"
        })
    except Exception as e:
        logger.error(f"market_fund_flow error: {e}")
        return error_response(500, f"获取资金流数据失败: {str(e)}")

@router.get("/market/fund_flow/industry")
async def industry_fund_flow():
    """行业资金流向"""
    import akshare as ak
    
    try:
        df = ak.stock_sector_fund_flow_summary(indicator="今日")
        
        result = []
        for _, row in df.iterrows():
            # 尝试获取主力净流入字段
            try:
                main_net = int(row.get("今日主力净流入-净额", 0) or 0)
            except (ValueError, TypeError):
                main_net = 0
            result.append({
                "name": str(row.get("名称", "")),
                "change_pct": float(row.get("今日涨跌幅", 0) or 0),
                "main_net": main_net,
            })
        
        return success_response({
            "items": result[:20],  # 前20个行业
            "total": len(result),
            "source": "akshare - stock_sector_fund_flow_summary"
        })
    except Exception as e:
        logger.error(f"industry_fund_flow error: {e}")
        return error_response(500, f"获取行业资金流失败: {str(e)}")
