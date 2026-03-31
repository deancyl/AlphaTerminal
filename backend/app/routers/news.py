"""
资讯流接口 - Phase 5
API 只读全局缓存，后台线程负责刷新（<50ms 响应）
"""
import logging
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/news/flash")
async def news_flash():
    """
    快讯瀑布流（只读缓存，后台刷新线程维护）
    响应时间 < 50ms
    任务3：禁用 Mock！缓存未就绪时返回空列表，前端展示"正在加载..."
    """
    from app.services.news_engine import get_cached_news, is_cache_ready

    if not is_cache_ready():
        logger.warning("[News] 缓存未就绪，返回空列表（禁止Mock降级）")
        return {"news": [], "source": "cache_empty", "total": 0}

    news = get_cached_news(limit=150)
    if not news:
        logger.warning("[News] 缓存为空")
        return {"news": [], "source": "cache_empty", "total": 0}

    return {"news": news, "source": "cache", "total": len(news)}


@router.get("/news/detail")
async def news_detail(url: str = Query(..., description="新闻原文 URL")):
    """
    抓取新闻原文正文（纯文本，剥离图片/脚本/样式）
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://finance.eastmoney.com/",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        r.encoding = r.apparent_encoding or "utf-8"

        soup = BeautifulSoup(r.text, "html.parser")

        # 移除所有噪声标签
        for tag in soup.find_all(["script", "style", "img", "svg", "iframe",
                                   "nav", "header", "footer", "aside"]):
            tag.decompose()

        # 提取所有 <p> 段落文字
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 20:
                paragraphs.append(text)

        content = "\n\n".join(paragraphs)

        if len(content) < 100:
            article = soup.find("article") or soup.find(
                "div", class_=lambda c: c and ("content" in c or "article" in c) if c else False
            )
            if article:
                content = article.get_text(separator="\n", strip=True)

        if len(content) < 50:
            return {"content": "原文解析失败（页面结构不支持自动提取），请点击链接查看网页。", "url": url}

        logger.info(f"[News] 成功抓取 {url}，提取 {len(content)} 字符")
        return {"content": content[:8000], "url": url}

    except Exception as e:
        logger.error(f"[News] news_detail 失败: {type(e).__name__}: {e}", exc_info=True)
        return {"content": "原文解析失败，请点击链接查看网页。", "url": url}


@router.get("/news/transcript/{video_id}")
async def video_transcript(video_id: str):
    """YouTube 字幕（走代理）"""
    from app.services.news_fetcher import fetch_youtube_transcript
    return fetch_youtube_transcript(video_id)
