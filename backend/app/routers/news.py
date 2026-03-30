"""
资讯流接口 - Phase 4
"""
from fastapi import APIRouter
from app.services.news_fetcher import get_mock_news

router = APIRouter()


@router.get("/news/flash")
async def news_flash():
    """快讯瀑布流（Mock）"""
    return {"news": get_mock_news()}


@router.get("/news/transcript/{video_id}")
async def video_transcript(video_id: str):
    """
    YouTube 字幕（走代理）
    若返回 400 表示代理被封，需用户配置可用住宅代理
    """
    from app.services.news_fetcher import fetch_youtube_transcript
    try:
        result = fetch_youtube_transcript(video_id)
        return result
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
