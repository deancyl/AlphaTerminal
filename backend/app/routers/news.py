"""
资讯流接口 - Phase 4
"""
import logging
from fastapi import APIRouter
from app.services.news_engine import fetch_latest_news, get_mock_news

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/news/flash")
async def news_flash():
    """快讯瀑布流（真实数据 + MD5 URL 去重）"""
    try:
        news = fetch_latest_news(limit=20)
        if not news:
            logger.warning("[News] 真实数据为空，降级至 Mock")
            return {"news": get_mock_news(), "source": "mock"}
        logger.info(f"[News] 返回 {len(news)} 条新闻")
        return {"news": news, "source": "engine"}
    except Exception as e:
        logger.error(f"[News] news_flash 失败: {type(e).__name__}: {e}", exc_info=True)
        return {"news": get_mock_news(), "source": "mock"}


@router.get("/news/transcript/{video_id}")
async def video_transcript(video_id: str):
    """
    YouTube 字幕（走代理）
    若返回 400 表示代理被封，需用户配置可用住宅代理
    """
    from app.services.news_fetcher import fetch_youtube_transcript
    result = fetch_youtube_transcript(video_id)
    return result
