"""
深度资讯抓取 - Phase 4
YouTube 字幕抓取：必须走代理（墙外）
国内数据：绕过代理（Phase 3 已处理）
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── YouTube 走代理（墙外资源）──────────────────────────────────────────
PROXY_YOUTUBE = "http://192.168.1.50:7897"


def fetch_youtube_transcript(video_id: str, lang: str = "zh-CN") -> dict:
    """
    抓取 YouTube 视频字幕，转为纯文本段落。

    Args:
        video_id: YouTube 视频 ID（如 "abc123XYZ"）
        lang:    优先字幕语言，默认中文 "zh-CN"，降级 "en"，自动翻译 "zh-Hans"

    Returns:
        {"title": str, "paragraphs": list[str], "duration": str, "source": str}
    """
    import httpx
    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
    from youtube_transcript_api.proxies import GenericProxyConfig

    logger.info(f"[YouTube] 正在抓取字幕 video_id={video_id}")

    # ── 代理配置：使用 GenericProxyConfig ──────────────────────────────
    proxy_cfg = GenericProxyConfig(PROXY_YOUTUBE)
    os.environ["http_proxy"]  = PROXY_YOUTUBE
    os.environ["https_proxy"] = PROXY_YOUTUBE

    try:
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_cfg)
        transcript_list = ytt_api.list(video_id)

        transcript = None
        for target_lang in [lang, "zh-Hans", "en"]:
            try:
                transcript = transcript_list.find_transcript([target_lang])
                logger.info(f"[YouTube] 找到字幕 lang={transcript.language_code}")
                break
            except NoTranscriptFound:
                continue

        # 尝试翻译（若无中文）
        if transcript is None:
            try:
                en_transcript = transcript_list.find_transcript(["en"])
                transcript = en_transcript.translate(lang)
                logger.info(f"[YouTube] 已翻译为 {lang}")
            except NoTranscriptFound:
                raise TranscriptsDisabled(f"video {video_id} 无任何可用字幕")

        # 拉取所有分段
        fetched = transcript.fetch()
        lines = [
            segment.text.strip().replace("\n", " ")
            for segment in fetched
            if segment.text.strip()
        ]

        # 合并为段落（每 ~200 字符一段）
        paragraphs = []
        buf = ""
        for line in lines:
            if len(buf) + len(line) > 200:
                if buf:
                    paragraphs.append(buf)
                buf = line
            else:
                buf = (buf + " " + line).strip()
        if buf:
            paragraphs.append(buf)

        total_sec = fetched[-1].start + fetched[-1].duration if fetched else 0
        m, s = divmod(int(total_sec), 60)
        duration = f"{m}:{s:02d}"

        # 尝试拉视频标题
        title = _fetch_youtube_title(video_id)

        logger.info(f"[YouTube] 抓取成功: {len(paragraphs)} 段, 时长 {duration}")
        return {
            "title":      title or f"Video {video_id}",
            "paragraphs": paragraphs,
            "duration":   duration,
            "source":     f"https://youtube.com/watch?v={video_id}",
        }

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.warning(f"[YouTube] 字幕不可用: {e}")
        raise ValueError(f"该视频无字幕或字幕不可下载: {video_id}")
    except VideoUnavailable as e:
        logger.error(f"[YouTube] 视频不可用: {e}")
        raise ValueError(f"视频不可用: {video_id}")
    except Exception as e:
        logger.error(f"[YouTube] 抓取失败: {type(e).__name__}: {e}", exc_info=True)
        raise RuntimeError(f"YouTube 字幕抓取失败: {e}")
    finally:
        # 恢复：清除代理环境，不影响后续国内请求
        os.environ.pop("http_proxy",  None)
        os.environ.pop("https_proxy", None)


def _fetch_youtube_title(video_id: str) -> Optional[str]:
    """通过 YouTube oEmbed API 获取视频标题（无需代理）"""
    import httpx
    try:
        r = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=5,
        )
        if r.status_code == 200:
            return r.json().get("title")
    except Exception:
        pass
    return None


def get_mock_news() -> list[dict]:
    """
    Mock 资讯数据（Phase 4 早期测试用）
    后续替换为真实爬虫
    """
    return [
        {
            "id":       "news001",
            "tag":      "🔴 突发",
            "title":    "央行宣布定向降准 0.25 个百分点，释放长期资金约 5000 亿元",
            "time":     "02:34",
            "source":   "央行官网",
            "url":      "#",
        },
        {
            "id":       "news002",
            "tag":      "📈 A股",
            "title":    "上证指数重返 3400 点，券商板块掀起涨停潮",
            "time":     "01:15",
            "source":   "东方财富",
            "url":      "#",
        },
        {
            "id":       "news003",
            "tag":      "🌏 港股",
            "title":    "恒生科技指数大涨 3.8%，南向资金净买入超 100 亿",
            "time":     "00:58",
            "source":   "经济通",
            "url":      "#",
        },
        {
            "id":       "news004",
            "tag":      "💎 宏观",
            "title":    "美国 2 月 CPI 超预期回落，市场押注美联储 6 月降息概率突破 70%",
            "time":     "00:41",
            "source":   "Bloomberg",
            "url":      "#",
        },
        {
            "id":       "news005",
            "tag":      "🖥️ AI",
            "title":    "OpenAI 发布 GPT-5 Turbo，上下文窗口扩展至 100 万 token",
            "time":     "00:22",
            "source":   "The Verge",
            "url":      "#",
        },
    ]
