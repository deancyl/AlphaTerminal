"""
市场数据接口 - Phase 3 真实数据
所有数据从 SQLite market_data_realtime 读取
"""
import time
from datetime import datetime
from fastapi import APIRouter
from app.db import get_latest_prices, get_price_history

router = APIRouter()

# 追踪的标的列表
INDEX_SYMBOLS = ["000001", "000300", "399001", "399006"]
RATE_SYMBOLS  = ["shibor_1d", "shibor_1w", "shibor_1m", "shibor_3m", "shibor_1y"]


@router.get("/market/overview")
async def market_overview():
    """
    市场概览 — 从 SQLite 读取最新行情
    """
    all_symbols = INDEX_SYMBOLS + RATE_SYMBOLS
    rows = get_latest_prices(all_symbols)

    markets = {}
    for r in rows:
        key = r["symbol"]
        if key in INDEX_SYMBOLS:
            markets[key] = {
                "name":       r["name"] or key,
                "index":      r["price"],
                "change_pct": r["change_pct"],
                "volume":     r["volume"],
                "status":     "交易中",
                "market":     r["market"],
            }
        elif key in RATE_SYMBOLS:
            markets[key] = {
                "name":       r["name"],
                "rate":       r["price"],
                "change_pct": None,
                "status":     "日更新",
            }

    # 基础资金面（当无真实数据时用 Mock 保底）
    fundamentals = {
        "shibor_1w": markets.get("shibor_1w", {}).get("rate", 1.82),
        "shibor_1y": markets.get("shibor_1y", {}).get("rate", 2.14),
    }

    return {
        "timestamp":    datetime.now().isoformat(),
        "markets":      markets,
        "fundamentals": fundamentals,
    }


@router.get("/market/indices")
async def market_indices():
    """A股指数列表"""
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


@router.get("/market/history/{symbol}")
async def market_history(symbol: str, limit: int = 100):
    """获取某个标的历史行情（用于图表）"""
    history = get_price_history(symbol, limit=limit)
    return {
        "symbol":   symbol,
        "timestamp": datetime.now().isoformat(),
        "history":  history,
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
