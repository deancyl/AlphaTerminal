"""
Mock 市场数据接口 - Phase 2 前后端联调专用
"""
from datetime import datetime
from fastapi import APIRouter

router = APIRouter()


@router.get("/market/overview")
async def market_overview():
    """市场概览 Mock 接口"""
    return {
        "timestamp": datetime.now().isoformat(),
        "markets": {
            "AShare": {
                "name": "A股上证",
                "index": 3342.27,
                "change": +1.23,
                "change_pct": +0.04,
                "volume": 2.87e9,
                "turnover": 4.12e11,
                "status": "交易中",
            },
            "HKShare": {
                "name": "港股恒生",
                "index": 18521.45,
                "change": -156.30,
                "change_pct": -0.84,
                "volume": 8.34e8,
                "turnover": 9.21e10,
                "status": "交易中",
            },
            "USStock": {
                "name": "美股纳斯达克",
                "index": 18234.56,
                "change": +89.12,
                "change_pct": +0.49,
                "volume": 4.21e9,
                "status": "收盘",
            },
            "Crypto": {
                "name": "BTC/USDT",
                "index": 67432.50,
                "change": +1243.80,
                "change_pct": +1.88,
                "volume": 2.83e10,
                "status": "24h",
            },
        },
        "fundamentals": {
            "shibor_1w": 1.82,
            "shibor_1y": 2.14,
            "usd_cny": 7.2512,
            "usd_index": 104.32,
            "gold_usd": 2034.5,
            "wti_oil": 78.43,
        },
    }


@router.get("/market/watchlist")
async def watchlist():
    """自选股 Mock 接口"""
    return {
        "timestamp": datetime.now().isoformat(),
        "stocks": [
            {"symbol": "000001", "name": "平安银行", "price": 12.34, "change_pct": +0.82, "volume": 3.2e7},
            {"symbol": "600519", "name": "贵州茅台", "price": 1688.0, "change_pct": -1.23, "volume": 1.1e6},
            {"symbol": "NVDA", "name": "NVIDIA", "price": 875.32, "change_pct": +2.14, "volume": 4.5e7},
            {"symbol": "BTC", "name": "Bitcoin", "price": 67432.50, "change_pct": +1.88, "volume": 2.83e10},
        ],
    }
