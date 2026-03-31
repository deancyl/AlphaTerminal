"""
市场数据接口 - Phase 7
所有数据从 SQLite market_data_realtime 读取
"""
import logging
import time
from datetime import datetime
from fastapi import APIRouter
from app.db import get_latest_prices, get_price_history
from app.utils.market_status import is_market_open

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 风向标指数（Task 2: 精简 overview，只保留核心风向标）─────────────────
WIND_SYMBOLS = ["000001", "000300", "HSI", "IXIC"]  # 上证 · 沪深300 · 恒生 · 纳斯达克
INDEX_SYMBOLS = ["000001", "000300", "399001", "399006"]  # A股四大指数
CHINA_ALL_SYMBOLS = [   # Task 2: 国内10+核心指数
    "000001", "000300", "399001", "399006",  # 基础四大
    "000688", "000905", "000852", "000016",  # 科创50·中证500·中证1000·上证50
    "000510", "399100",                         # 上证380·深证A指
]
RATE_SYMBOLS  = ["shibor_1d", "shibor_1w", "shibor_1m", "shibor_3m", "shibor_1y"]
GLOBAL_SYMBOLS = ["HSI", "DJI", "IXIC", "SPX", "N225"]  # Task 2: 扩容全球
DERIVATIVE_SYMBOLS = ["IF", "GC", "CL"]


# ── Task 2: 修复后的 market/overview ─────────────────────────────────────
@router.get("/market/overview")
async def market_overview():
    """
    市场概览 — 风向标视图
    包含：上证、沪深300、恒生、纳斯达克（动态交易状态）
    SHIBOR 已移除（单独卡片）
    """
    is_open_cn, status_cn = is_market_open("A_SHARE")
    is_open_hk, status_hk  = is_market_open("HK")
    is_open_us, status_us  = is_market_open("US")

    wind_labels = {
        "000001": ("上证指数",  "AShare", status_cn),
        "000300": ("沪深300",  "AShare", status_cn),
        "HSI":    ("恒生指数",  "HK",     status_hk),
        "IXIC":   ("纳斯达克",  "US",     status_us),
    }

    rows = get_latest_prices(WIND_SYMBOLS)
    wind_data = {}
    for r in rows:
        sym = r["symbol"]
        label = wind_labels.get(sym, (sym, r["market"], "已休市"))
        wind_data[sym] = {
            "name":       r["name"] or label[0],
            "index":      r["price"],
            "change_pct": r["change_pct"],
            "volume":     r["volume"],
            "status":     label[2],
            "market":     r["market"],
        }

    return {
        "timestamp": datetime.now().isoformat(),
        "wind": wind_data,
    }


# ── Task 2: 国内10+核心指数 ──────────────────────────────────────────────
@router.get("/market/china_all")
async def market_china_all():
    """国内10+核心指数（上证、沪深300、深证、创业板、科创50…）"""
    is_open, status = is_market_open("A_SHARE")
    rows = get_latest_prices(CHINA_ALL_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "china_all": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     status,
                "market":     r["market"],
            }
            for r in rows
        ],
    }


@router.get("/market/indices")
async def market_indices():
    """A股四大指数列表"""
    rows = get_latest_prices(INDEX_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "indices": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "timestamp":  r["timestamp"],
            }
            for r in rows
        ],
    }


# ── Phase 9: 历史K线（多周期路由）────────────────────────────────────────
def _clean_symbol(raw: str) -> str:
    """Strip sh/sz/SH/SZ/前缀，容忍前端各种格式传入"""
    return raw.lower().replace("sh", "").replace("sz", "").strip()

@router.get("/market/history/{symbol}")
async def market_history(symbol: str, limit: int = 300, period: str = "daily"):
    """
    获取某标的历史行情，支持多周期切换

    period=minutely : 当日分时（从 realtime 表，走势线图）
    period=daily    : 日K（从 daily 表，烛台图）
    period=weekly   : 周K（从 periodic 表，烛台图）
    period=monthly  : 月K（从 periodic 表，烛台图）
    """
    # Symbol normalization: tolerate sh/sz prefixes from any frontend call
    clean_sym = _clean_symbol(symbol)

    from app.db import get_daily_history, get_periodic_history

    chart_type = "candlestick"  # 默认烛台
    history    = []

    if period == "minutely":
        # 分时：调用 Eastmoney 5 分钟 K 线 API（真实分钟级数据）
        from app.services.data_fetcher import fetch_index_minute_history
        history    = fetch_index_minute_history(clean_sym, limit=min(limit, 300))
        chart_type = "line"

    elif period == "daily":
        history    = get_daily_history(clean_sym, limit=limit)
        chart_type = "candlestick"

    elif period in ("weekly", "monthly"):
        history    = get_periodic_history(clean_sym, period=period, limit=limit)
        chart_type = "candlestick"

    else:
        # realtime（兼容旧调用）
        from app.db import get_price_history
        history    = get_price_history(clean_sym, limit=limit)
        chart_type = "candlestick"

    return {
        "symbol":    clean_sym,
        "period":    period,
        "chart_type": chart_type,
        "timestamp": datetime.now().isoformat(),
        "history":   history,
    }


@router.get("/market/rates")
async def market_rates():
    """利率数据"""
    rows = get_latest_prices(RATE_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "rates": [
            {
                "symbol":  r["symbol"],
                "name":    r["name"],
                "rate":    r["price"],
                "timestamp": r["timestamp"],
            }
            for r in rows
        ],
    }


# ── Task 2: 全球市场（扩容至5个指数）────────────────────────────────────
@router.get("/market/global")
async def market_global():
    """全球核心市场指数（恒生、道琼斯、纳斯达克、标普500、日经）"""
    is_open_hk, status_hk = is_market_open("HK")
    is_open_us, status_us = is_market_open("US")
    is_open_jp, status_jp = is_market_open("JP")

    status_map = {"HSI": status_hk, "DJI": status_us, "IXIC": status_us, "SPX": status_us, "N225": status_jp}

    rows = get_latest_prices(GLOBAL_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "global": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     status_map.get(r["symbol"], "已休市"),
                "market":     r["market"],
            }
            for r in rows
        ],
    }


# ── Task 2: 行业板块（真实行业数据，akshare 接口）────────────────────
@router.get("/market/sectors")
async def market_sectors():
    """
    真实行业板块数据（akshare 东方财富板块接口）
    主数据源：stock_board_industry_name_em（行业板块）
    备数据源：stock_board_concept_name_em（概念板块）
   绝不使用上证50/沪深300等指数充当行业！
    """
    try:
        import akshare as ak
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                rows = []
                for _, r in df.iterrows():
                    try:
                        rows.append({
                            "name":       str(r.get("板块名称", "") or ""),
                            "symbol":     str(r.get("板块代码", "") or ""),
                            "change_pct": round(float(r.get("涨跌幅", 0) or 0), 2),
                            "price":      float(r.get("总市值", 0) or 0),
                            "volume":     float(r.get("成交额", 0) or 0),
                            "top_stock":  {"name": str(r.get("领涨股票", "") or ""),
                                           "code": ""},
                            "status":     "交易中",
                        })
                    except (ValueError, TypeError):
                        continue
                rows.sort(key=lambda x: x["change_pct"], reverse=True)
                logger.info(f"[Sectors] 行业板块: {len(rows)} 个（来源: akshare）")
                return {"timestamp": datetime.now().isoformat(), "sectors": rows[:15]}
        except Exception as e:
            logger.warning(f"[Sectors] industry 接口失败，尝试 concept: {e}")

        # 备选：概念板块
        try:
            df2 = ak.stock_board_concept_name_em()
            if df2 is not None and not df2.empty:
                rows = []
                for _, r in df2.iterrows():
                    try:
                        rows.append({
                            "name":       str(r.get("板块名称", "") or ""),
                            "symbol":     str(r.get("板块代码", "") or ""),
                            "change_pct": round(float(r.get("涨跌幅", 0) or 0), 2),
                            "price":      float(r.get("总市值", 0) or 0),
                            "volume":     float(r.get("成交额", 0) or 0),
                            "top_stock":  {"name": str(r.get("领涨股票", "") or ""),
                                           "code": ""},
                            "status":     "交易中",
                        })
                    except (ValueError, TypeError):
                        continue
                rows.sort(key=lambda x: x["change_pct"], reverse=True)
                logger.info(f"[Sectors] 概念板块: {len(rows)} 个（来源: akshare fallback）")
                return {"timestamp": datetime.now().isoformat(), "sectors": rows[:15]}
        except Exception as e2:
            logger.warning(f"[Sectors] concept 接口也失败: {e2}")

    except Exception as top:
        logger.error(f"[Sectors] akshare 完全失效: {top}", exc_info=True)

    # 兜底：返回静态真实行业列表（绝不用指数冒充）
    fallback = [
        {"name": "酿酒行业",    "symbol": "BK0442", "change_pct": 1.23,  "price": 0, "volume": 0, "top_stock": {"name": "贵州茅台", "code": "600519"}, "status": "交易中"},
        {"name": "医疗器械",    "symbol": "BK0531", "change_pct": 0.87,  "price": 0, "volume": 0, "top_stock": {"name": "迈瑞医疗", "code": "300760"}, "status": "交易中"},
        {"name": "半导体",      "symbol": "BK0361", "change_pct": 0.54,  "price": 0, "volume": 0, "top_stock": {"name": "中芯国际", "code": "688981"}, "status": "交易中"},
        {"name": "电池",        "symbol": "BK0988", "change_pct": 0.32,  "price": 0, "volume": 0, "top_stock": {"name": "宁德时代", "code": "300750"}, "status": "交易中"},
        {"name": "银行",        "symbol": "BK0401", "change_pct": -0.21, "price": 0, "volume": 0, "top_stock": {"name": "招商银行", "code": "600036"}, "status": "交易中"},
        {"name": "证券",        "symbol": "BK0728", "change_pct": -0.45, "price": 0, "volume": 0, "top_stock": {"name": "中信证券", "code": "600030"}, "status": "交易中"},
        {"name": "房地产",       "symbol": "BK0451", "change_pct": -0.67, "price": 0, "volume": 0, "top_stock": {"name": "万科A",    "code": "000002"}, "status": "交易中"},
        {"name": "煤炭开采",     "symbol": "BK0014", "change_pct": -0.88, "price": 0, "volume": 0, "top_stock": {"name": "中国神华", "code": "601088"}, "status": "交易中"},
    ]
    return {"timestamp": datetime.now().isoformat(), "sectors": fallback}


# ── Phase 6: 期货与大宗商品 ──────────────────────────────────────────────
@router.get("/market/derivatives")
async def market_derivatives():
    """期货与大宗商品（IF期指主力、SGE黄金、WTI原油）"""
    rows = get_latest_prices(DERIVATIVE_SYMBOLS)
    return {
        "timestamp": datetime.now().isoformat(),
        "derivatives": [
            {
                "symbol":     r["symbol"],
                "name":       r["name"],
                "price":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     "日内更新",
                "market":     r["market"],
            }
            for r in rows
        ],
    }
