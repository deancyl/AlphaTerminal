"""
市场情绪路由 - Phase 2
"""
import logging
from fastapi import APIRouter
from app.services.sentiment_engine import get_sentiment, is_sentiment_ready

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/market/sentiment")
async def market_sentiment():
    """
    A股市场情绪温度计
    返回：上涨家数、下跌家数、平盘家数、涨停数、跌停数、上涨比例（0.0~1.0）
    """
    if not is_sentiment_ready():
        return {
            "advance": 0, "decline": 0, "unchanged": 0,
            "limit_up": 0, "limit_down": 0, "total": 0,
            "up_ratio": 0.0, "timestamp": "计算中...",
        }
    return get_sentiment()
