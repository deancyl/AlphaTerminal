"""
资讯流接口 - Phase 5
API 只读全局缓存，后台线程负责刷新（<50ms 响应）

Phase B: 统一 API 响应格式
- 所有响应使用标准格式: {code, message, data, timestamp}
- code: 0 表示成功，非 0 表示错误
"""
import asyncio
import logging
import time
import httpx
from fastapi import APIRouter, HTTPException, Query
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/news/flash")
async def news_flash():
    """
    快讯瀑布流（只读缓存，后台刷新线程维护）
    响应时间 < 50ms
    禁用 Mock！缓存未就绪时返回空列表
    """
    from app.services.news_engine import get_cached_news, is_cache_ready

    if not is_cache_ready():
        logger.warning("[News] 缓存未就绪，返回空列表")
        return success_response({"news": [], "source": "cache_empty", "total": 0})

    news = get_cached_news(limit=150)
    if not news:
        logger.warning("[News] 缓存为空")
        return success_response({"news": [], "source": "cache_empty", "total": 0})

    return success_response({"news": news, "source": "cache", "total": len(news)})


@router.post("/news/force_refresh")
async def news_force_refresh():
    """
    穿透式强制刷新（Phase 3.6 UX 整改）：
    同步执行真实网络抓取，等待完成后再返回最新数据。
    前端手动刷新时调用此接口，确保拿到此刻的外网最新数据。
    """
    import asyncio
    from app.services.news_engine import get_cached_news, is_cache_ready, refresh_news_cache

    async def _do():
        # 在线程池中执行同步的 refresh_news_cache(background=False)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, refresh_news_cache, False)

    # 记录刷新前的缓存条数，用于判断是否为"旧数据"
    stale_count = len(get_cached_news(limit=200)) if is_cache_ready() else 0

    try:
        logger.info("[News] force_refresh: 开始同步抓取...")
        await _do()
        news = get_cached_news(limit=150)
        logger.info(f"[News] force_refresh: 获取到 {len(news)} 条")
        # 有新数据或本来就有缓存 → items_stale=false；完全空白 → items_stale=true
        items_stale = (len(news) == 0 and stale_count == 0)
        return success_response({
            "news":        news,
            "source":      "force_refresh",
            "total":       len(news),
            "items_stale": items_stale,
        })
    except Exception as e:
        logger.error(f"[News] force_refresh 失败: {type(e).__name__}: {e}", exc_info=True)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"强制刷新失败: {str(e)}",
            {
                "news":        [],
                "source":      "error",
                "total":       0,
                "error":       str(e),
                "items_stale": True,
                "stale_count": stale_count,
            }
        )


@router.get("/news/detail")
async def news_detail(url: str = Query(..., description="新闻原文 URL")):
    """
    抓取新闻原文正文（纯文本，剥离图片/脚本/样式）
    SSRF 防护：仅允许 http/https，拒绝内网地址
    """
    try:
        # ── SSRF 防护：校验 URL ────────────────────────────────────
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""

        # 仅允许 http/https
        if parsed.scheme not in ("http", "https"):
            return error_response(1, "仅支持 http/https 协议", {"url": url})

        # 空 hostname 防护：绕过所有后续检查（如 http:///path）
        if not host:
            return error_response(1, "URL 缺少有效 hostname", {"url": url})

        # 禁止访问内网/云元数据地址
        BLOCKED_HOSTS = {
            "localhost", "127.0.0.1", "0.0.0.0", "::1", "::",
            "169.254.169.254",      # AWS/GCP/Alibaba cloud metadata
            "metadata.google.internal",
        }
        # 禁止 10.x.x.x, 172.16-31.x.x, 192.168.x.x 等私有网段
        import ipaddress
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                return error_response(1, "禁止访问内网地址", {"url": url})
        except ValueError:
            # 不是 IP 地址，检查域名
            if host in BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
                return error_response(1, "禁止访问内网地址", {"url": url})

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
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            text_content = r.text[:100 * 1024]  # 最多读取 100KB

        soup = BeautifulSoup(text_content, "html.parser")

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
            return success_response({"content": "原文解析失败（页面结构不支持自动提取），请点击链接查看网页。", "url": url})

        logger.info(f"[News] 成功抓取 {url}，提取 {len(content)} 字符")
        return success_response({"content": content[:8000], "url": url})

    except Exception as e:
        logger.error(f"[News] news_detail 失败: {type(e).__name__}: {e}", exc_info=True)
        return success_response({"content": "原文解析失败，请点击链接查看网页。", "url": url})


@router.get("/news/transcript/{video_id}")
async def video_transcript(video_id: str):
    """YouTube 字幕（走代理）"""
    from app.services.news_fetcher import fetch_youtube_transcript
    return fetch_youtube_transcript(video_id)


@router.get("/news/events/{symbol}")
async def news_events_for_symbol(
    symbol: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of events to return")
):
    """
    Get news events for a specific stock symbol for chart markers.
    Returns news with date, headline, type (bullish/bearish/neutral), and suggested price.
    
    Used by BaseKLineChart to display news markers on the K-line chart.
    """
    try:
        clean_symbol = symbol.replace("sh", "").replace("sz", "").replace("hk", "").replace("us", "")
        
        from app.services.news_engine import get_cached_news, is_cache_ready
        
        if not is_cache_ready():
            return success_response({"events": [], "symbol": symbol, "total": 0})
        
        all_news = get_cached_news(limit=500)
        
        events = []
        for news in all_news:
            title = news.get("title", "")
            if clean_symbol in title or symbol in title:
                bullish_keywords = ["利好", "上涨", "突破", "新高", "增长", "盈利", "增持", "回购", "中标", "签约"]
                bearish_keywords = ["利空", "下跌", "暴跌", "亏损", "减持", "质押", "违约", "诉讼", "调查", "处罚"]
                
                type_ = "neutral"
                if any(k in title for k in bullish_keywords):
                    type_ = "bullish"
                elif any(k in title for k in bearish_keywords):
                    type_ = "bearish"
                
                time_str = news.get("time", "")
                date = time_str.split(" ")[0] if " " in time_str else time_str[:10]
                
                if date and len(date) == 10:
                    events.append({
                        "date": date,
                        "headline": title,
                        "type": type_,
                        "price": None,
                        "url": news.get("url", ""),
                        "source": news.get("source", ""),
                    })
        
        events = events[:limit]
        
        return success_response({
            "events": events,
            "symbol": symbol,
            "total": len(events)
        })
        
    except Exception as e:
        logger.error(f"[News] news_events_for_symbol failed: {type(e).__name__}: {e}", exc_info=True)
        return error_response(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to get news events: {str(e)}",
            {"events": [], "symbol": symbol, "total": 0}
        )
