"""
资讯流接口 - Phase 4
"""
import logging
import re
from typing import Optional
from fastapi import APIRouter, Query
from app.services.news_engine import fetch_latest_news, get_mock_news

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 反爬白名单（仅允许以下域名）──────────────────────────────────────────
SAFE_NEWS_DOMAINS = [
    "eastmoney.com", "sina.com.cn", "finance.sina.com.cn",
    "qq.com", "ifeng.com", "cls.cn", "xinhuanet.com",
    "stock.eastmoney.com", "finance.eastmoney.com",
    "cj.sina.com.cn", "tech.sina.com.cn",
]


def _is_safe_url(url: str) -> bool:
    """仅允许白名单域名，阻止 SSRF"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in SAFE_NEWS_DOMAINS)
    except Exception:
        return False


@router.get("/news/flash")
async def news_flash():
    """快讯瀑布流（真实数据 + MD5 URL 去重）"""
    try:
        news = fetch_latest_news(limit=150)
        if not news:
            logger.warning("[News] 真实数据为空，降级至 Mock")
            return {"news": get_mock_news(), "source": "mock", "total": len(get_mock_news())}
        logger.info(f"[News] 返回 {len(news)} 条新闻")
        return {"news": news, "source": "engine", "total": len(news)}
    except Exception as e:
        logger.error(f"[News] news_flash 失败: {type(e).__name__}: {e}", exc_info=True)
        return {"news": get_mock_news(), "source": "mock", "total": len(get_mock_news())}


@router.get("/news/detail")
async def news_detail(url: str = Query(..., description="新闻原文 URL")):
    """
    抓取新闻原文正文（纯文本，剥离图片/脚本/样式）
    仅支持白名单域名，防 SSRF
    """
    if not _is_safe_url(url):
        logger.warning(f"[News] 非法域名被拦截: {url}")
        return {"content": "原文解析失败（域名不在白名单内），请点击链接查看网页。", "url": url}

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
            if len(text) > 20:  # 过滤过短噪声
                paragraphs.append(text)

        content = "\n\n".join(paragraphs)

        if len(content) < 100:
            # 降级：取 <article> 或 class~=content 的 div
            article = soup.find("article") or soup.find("div", class_=re.compile("content|article", re.I))
            if article:
                content = article.get_text(separator="\n", strip=True)

        if len(content) < 50:
            return {
                "content": "原文解析失败（页面结构不支持自动提取），请点击链接查看网页。",
                "url": url,
            }

        logger.info(f"[News] 成功抓取 {url}，提取 {len(content)} 字符")
        return {"content": content[:8000], "url": url}   # 上限 8000 字

    except Exception as e:
        logger.error(f"[News] news_detail 失败: {type(e).__name__}: {e}", exc_info=True)
        return {"content": "原文解析失败，请点击链接查看网页。", "url": url}


@router.get("/news/transcript/{video_id}")
async def video_transcript(video_id: str):
    """
    YouTube 字幕（走代理）
    若返回 400 表示代理被封，需用户配置可用住宅代理
    """
    from app.services.news_fetcher import fetch_youtube_transcript
    result = fetch_youtube_transcript(video_id)
    return result
